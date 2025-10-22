"""Persistence helpers for QA run summaries and creative review."""

from __future__ import annotations

from datetime import datetime
from typing import Iterable, Protocol
from uuid import UUID

from sqlalchemy import Select, desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..domain.qa import (
    QAFinding,
    QAFindingCreate,
    QAFindingUpdate,
    QAReview,
    QAReviewCreate,
    QAReviewUpdate,
    QARun,
    QARunCreate,
    QARunDetail,
)
from ..models.qa import QAFindingModel, QAReviewModel, QARunModel


class QARunRepository(Protocol):
    async def record_run(self, org_id: UUID, payload: QARunCreate) -> QARunDetail: ...

    async def list_runs(
        self, org_id: UUID, *, limit: int = 20, offset: int = 0
    ) -> list[QARun]: ...

    async def count_runs(self, org_id: UUID) -> int: ...

    async def get_run(self, org_id: UUID, run_id: UUID) -> QARunDetail | None: ...

    async def list_findings(self, org_id: UUID, run_id: UUID) -> list[QAFinding]: ...

    async def get_finding(
        self, org_id: UUID, finding_id: UUID
    ) -> QAFinding | None: ...

    async def create_findings(
        self,
        org_id: UUID,
        run_id: UUID,
        findings: Iterable[QAFindingCreate],
        *,
        commit: bool = True,
    ) -> list[QAFinding]: ...

    async def update_finding(
        self, org_id: UUID, finding_id: UUID, payload: QAFindingUpdate
    ) -> QAFinding | None: ...

    async def create_review(
        self, org_id: UUID, run_id: UUID, payload: QAReviewCreate
    ) -> QAReview: ...

    async def list_reviews(self, org_id: UUID, run_id: UUID) -> list[QAReview]: ...

    async def update_review(
        self, org_id: UUID, review_id: UUID, payload: QAReviewUpdate
    ) -> QAReview | None: ...


class SqlAlchemyQARunRepository(QARunRepository):
    """Stores QA run summaries, findings, and approvals in Postgres."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def record_run(self, org_id: UUID, payload: QARunCreate) -> QARunDetail:
        run_fields = payload.model_dump(exclude={"findings"})
        run_fields["failure_artifact_ids"] = [
            str(value) for value in run_fields.get("failure_artifact_ids", [])
        ]
        model = QARunModel(org_id=org_id, **run_fields)
        self._session.add(model)
        await self._session.flush()
        created_findings = await self.create_findings(
            org_id=org_id,
            run_id=model.id,
            findings=payload.findings,
            commit=False,
        )
        await self._session.commit()
        latest_review = await self._latest_review(model.id)
        return self._build_detail(model, created_findings, [], latest_review)

    async def list_runs(
        self, org_id: UUID, *, limit: int = 20, offset: int = 0
    ) -> list[QARun]:
        stmt: Select[tuple[QARunModel]] = (
            select(QARunModel)
            .where(QARunModel.org_id == org_id)
            .options(selectinload(QARunModel.reviews))
            .order_by(QARunModel.recorded_at.desc())
            .offset(offset)
            .limit(limit)
        )
        rows = (await self._session.execute(stmt)).scalars().all()
        runs: list[QARun] = []
        for row in rows:
            latest_review = self._select_latest_review(row.reviews)
            run = self._build_run(row, latest_review)
            runs.append(run)
        return runs

    async def count_runs(self, org_id: UUID) -> int:
        stmt = select(func.count()).where(QARunModel.org_id == org_id)
        result = await self._session.execute(stmt)
        return int(result.scalar_one())

    async def get_run(self, org_id: UUID, run_id: UUID) -> QARunDetail | None:
        stmt = (
            select(QARunModel)
            .where(QARunModel.org_id == org_id, QARunModel.id == run_id)
            .options(
                selectinload(QARunModel.findings),
                selectinload(QARunModel.reviews),
            )
        )
        model = (await self._session.execute(stmt)).scalar_one_or_none()
        if model is None:
            return None
        latest_review = self._select_latest_review(model.reviews)
        findings = [QAFinding.model_validate(item) for item in model.findings]
        reviews = [QAReview.model_validate(item) for item in model.reviews]
        return self._build_detail(model, findings, reviews, latest_review)

    async def list_findings(self, org_id: UUID, run_id: UUID) -> list[QAFinding]:
        stmt = (
            select(QAFindingModel)
            .where(
                QAFindingModel.org_id == org_id,
                QAFindingModel.run_id == run_id,
            )
            .order_by(desc(QAFindingModel.created_at))
        )
        result = await self._session.execute(stmt)
        return [QAFinding.model_validate(row) for row in result.scalars().all()]

    async def get_finding(
        self, org_id: UUID, finding_id: UUID
    ) -> QAFinding | None:
        stmt = select(QAFindingModel).where(
            QAFindingModel.org_id == org_id,
            QAFindingModel.id == finding_id,
        )
        model = (await self._session.execute(stmt)).scalar_one_or_none()
        if model is None:
            return None
        return QAFinding.model_validate(model)

    async def create_findings(
        self,
        org_id: UUID,
        run_id: UUID,
        findings: Iterable[QAFindingCreate],
        *,
        commit: bool = True,
    ) -> list[QAFinding]:
        created: list[QAFinding] = []
        for finding in findings:
            data = finding.model_dump()
            data["reference_artifact_ids"] = [
                str(value) for value in data.get("reference_artifact_ids", [])
            ]
            if data.get("overlay_metadata") is None:
                data["overlay_metadata"] = {}
            if data.get("assignee_id") is not None and data.get("assigned_at") is None:
                data["assigned_at"] = datetime.utcnow()
            if data.get("assignee_id") is None and "assigned_at" not in data:
                data["assigned_at"] = None
            model = QAFindingModel(
                org_id=org_id,
                run_id=run_id,
                **data,
            )
            self._session.add(model)
            await self._session.flush()
            created.append(QAFinding.model_validate(model))
        if commit:
            await self._session.commit()
        return created

    async def update_finding(
        self, org_id: UUID, finding_id: UUID, payload: QAFindingUpdate
    ) -> QAFinding | None:
        stmt = select(QAFindingModel).where(
            QAFindingModel.org_id == org_id,
            QAFindingModel.id == finding_id,
        )
        model = (await self._session.execute(stmt)).scalar_one_or_none()
        if model is None:
            return None
        data = payload.model_dump(exclude_unset=True)
        if "reference_artifact_ids" in data and data["reference_artifact_ids"] is not None:
            data["reference_artifact_ids"] = [
                str(value) for value in data["reference_artifact_ids"]
            ]
        if "overlay_metadata" in data and data["overlay_metadata"] is None:
            data["overlay_metadata"] = {}
        if "assignee_id" in data:
            if data["assignee_id"] is not None and data.get("assigned_at") is None:
                data["assigned_at"] = datetime.utcnow()
            if data["assignee_id"] is None and "assigned_at" not in data:
                data["assigned_at"] = None
        for key, value in data.items():
            setattr(model, key, value)
        model.updated_at = datetime.utcnow()
        await self._session.flush()
        await self._session.commit()
        return QAFinding.model_validate(model)

    async def create_review(
        self, org_id: UUID, run_id: UUID, payload: QAReviewCreate
    ) -> QAReview:
        model = QAReviewModel(
            org_id=org_id,
            run_id=run_id,
            **payload.model_dump(),
        )
        self._session.add(model)
        await self._session.flush()
        await self._session.commit()
        return QAReview.model_validate(model)

    async def list_reviews(self, org_id: UUID, run_id: UUID) -> list[QAReview]:
        stmt = (
            select(QAReviewModel)
            .where(
                QAReviewModel.org_id == org_id,
                QAReviewModel.run_id == run_id,
            )
            .order_by(desc(QAReviewModel.created_at))
        )
        result = await self._session.execute(stmt)
        return [QAReview.model_validate(row) for row in result.scalars().all()]

    async def update_review(
        self, org_id: UUID, review_id: UUID, payload: QAReviewUpdate
    ) -> QAReview | None:
        stmt = select(QAReviewModel).where(
            QAReviewModel.org_id == org_id,
            QAReviewModel.id == review_id,
        )
        model = (await self._session.execute(stmt)).scalar_one_or_none()
        if model is None:
            return None
        data = payload.model_dump(exclude_unset=True)
        for key, value in data.items():
            setattr(model, key, value)
        model.updated_at = datetime.utcnow()
        await self._session.flush()
        await self._session.commit()
        return QAReview.model_validate(model)

    async def _latest_review(self, run_id: UUID) -> QAReview | None:
        stmt = (
            select(QAReviewModel)
            .where(QAReviewModel.run_id == run_id)
            .order_by(desc(QAReviewModel.created_at))
            .limit(1)
        )
        latest = (await self._session.execute(stmt)).scalar_one_or_none()
        if latest is None:
            return None
        return QAReview.model_validate(latest)

    def _select_latest_review(
        self, reviews: Iterable[QAReviewModel]
    ) -> QAReview | None:
        latest_model = None
        for review in reviews:
            if latest_model is None or review.created_at > latest_model.created_at:
                latest_model = review
        if latest_model is None:
            return None
        return QAReview.model_validate(latest_model)

    def _build_run(
        self, model: QARunModel, latest_review: QAReview | None
    ) -> QARun:
        run = QARun.model_validate(model)
        run.latest_review = latest_review
        return run

    def _build_detail(
        self,
        model: QARunModel,
        findings: list[QAFinding],
        reviews: list[QAReview],
        latest_review: QAReview | None,
    ) -> QARunDetail:
        detail = QARunDetail.model_validate(model)
        detail.findings = findings
        detail.reviews = reviews
        detail.latest_review = latest_review
        return detail
