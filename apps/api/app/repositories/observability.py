from __future__ import annotations

from collections import defaultdict
from typing import Protocol
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..domain.observability import (
    Metric,
    MetricCreate,
    MetricSummary,
    SLOReport,
    SLOStatus,
    compute_summary,
)
from ..domain.observability import MetricType
from ..models.observability import MetricModel


class ObservabilityRepository(Protocol):
    async def record_metric(self, org_id: UUID, payload: MetricCreate) -> Metric: ...

    async def list_metrics(
        self,
        org_id: UUID,
        *,
        name: str | None = None,
        limit: int = 100,
    ) -> list[Metric]: ...

    async def summarize_metrics(
        self, org_id: UUID, *, name: str | None = None
    ) -> MetricSummary: ...

    async def evaluate_slo(
        self,
        org_id: UUID,
        *,
        name: str,
        target_value: float,
        unit: str,
    ) -> SLOReport: ...


class InMemoryObservabilityRepository:
    """Volatile observability storage for the bootstrap phase."""

    def __init__(self) -> None:
        self._metrics: dict[UUID, list[Metric]] = defaultdict(list)

    async def record_metric(self, org_id: UUID, payload: MetricCreate) -> Metric:
        metric = Metric(org_id=org_id, **payload.model_dump())
        self._metrics[org_id].append(metric)
        return metric

    async def list_metrics(
        self,
        org_id: UUID,
        *,
        name: str | None = None,
        limit: int = 100,
    ) -> list[Metric]:
        items = list(self._metrics.get(org_id, []))
        if name is not None:
            items = [metric for metric in items if metric.name == name]
        items.sort(key=lambda metric: metric.recorded_at, reverse=True)
        return items[:limit]

    async def summarize_metrics(
        self, org_id: UUID, *, name: str | None = None
    ) -> MetricSummary:
        items = list(self._metrics.get(org_id, []))
        if name is not None:
            items = [metric for metric in items if metric.name == name]
        if not items:
            metric_name = name or "metrics"
            return compute_summary(metric_name, MetricType.GAUGE, [])
        metric_name = name or items[0].name
        metric_type = items[0].metric_type
        return compute_summary(metric_name, metric_type, items)

    async def evaluate_slo(
        self,
        org_id: UUID,
        *,
        name: str,
        target_value: float,
        unit: str,
    ) -> SLOReport:
        items = [
            metric
            for metric in self._metrics.get(org_id, [])
            if metric.name == name
        ]
        if not items:
            return SLOReport(
                name=name,
                target_value=target_value,
                unit=unit,
                sample_count=0,
                p95=None,
                status=SLOStatus.UNKNOWN,
            )
        summary = compute_summary(name, items[0].metric_type, items)
        p95 = summary.p95
        status = (
            SLOStatus.HEALTHY
            if p95 is not None and p95 <= target_value
            else SLOStatus.BREACHED
        )
        return SLOReport(
            name=name,
            target_value=target_value,
            unit=unit,
            sample_count=summary.count,
            p95=p95,
            status=status,
        )


class SqlAlchemyObservabilityRepository(ObservabilityRepository):
    """Persists metrics and summaries to Postgres."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def record_metric(self, org_id: UUID, payload: MetricCreate) -> Metric:
        model = MetricModel(org_id=org_id, **payload.model_dump())
        self._session.add(model)
        await self._session.flush()
        await self._session.commit()
        return Metric.model_validate(model)

    async def list_metrics(
        self,
        org_id: UUID,
        *,
        name: str | None = None,
        limit: int = 100,
    ) -> list[Metric]:
        query = select(MetricModel).where(MetricModel.org_id == org_id)
        if name is not None:
            query = query.where(MetricModel.name == name)
        query = query.order_by(MetricModel.recorded_at.desc()).limit(limit)
        result = await self._session.execute(query)
        return [Metric.model_validate(row) for row in result.scalars().all()]

    async def summarize_metrics(
        self, org_id: UUID, *, name: str | None = None
    ) -> MetricSummary:
        query = select(MetricModel).where(MetricModel.org_id == org_id)
        if name is not None:
            query = query.where(MetricModel.name == name)
        result = await self._session.execute(query)
        metrics = [Metric.model_validate(row) for row in result.scalars().all()]
        if not metrics:
            metric_name = name or "metrics"
            return compute_summary(metric_name, MetricType.GAUGE, [])
        metric_name = name or metrics[0].name
        return compute_summary(metric_name, metrics[0].metric_type, metrics)

    async def evaluate_slo(
        self,
        org_id: UUID,
        *,
        name: str,
        target_value: float,
        unit: str,
    ) -> SLOReport:
        metrics = await self.list_metrics(org_id, name=name, limit=1000)
        if not metrics:
            return SLOReport(
                name=name,
                target_value=target_value,
                unit=unit,
                sample_count=0,
                p95=None,
                status=SLOStatus.UNKNOWN,
            )
        summary = compute_summary(name, metrics[0].metric_type, metrics)
        p95 = summary.p95
        status = (
            SLOStatus.HEALTHY
            if p95 is not None and p95 <= target_value
            else SLOStatus.BREACHED
        )
        return SLOReport(
            name=name,
            target_value=target_value,
            unit=unit,
            sample_count=summary.count,
            p95=p95,
            status=status,
        )
