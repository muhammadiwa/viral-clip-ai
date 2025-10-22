from __future__ import annotations

from datetime import datetime
from enum import Enum
from math import floor
from typing import Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, Field

from .pagination import PaginationMeta


class MetricType(str, Enum):
    """Supported metric types exposed through the observability API."""

    GAUGE = "gauge"
    COUNTER = "counter"
    HISTOGRAM = "histogram"


class MetricBase(BaseModel):
    """Shared fields for observability metric payloads."""

    name: str = Field(..., min_length=3, max_length=128)
    metric_type: MetricType = Field(default=MetricType.GAUGE)
    value: float = Field(..., description="Recorded metric value as a floating point number")
    labels: dict[str, str] = Field(default_factory=dict)
    resource_type: Optional[str] = Field(
        default=None,
        max_length=64,
        description="Optional resource classification such as job, video, or project",
    )
    resource_id: Optional[UUID] = Field(
        default=None,
        description="Optional resource identifier for drill-down views",
    )


class MetricCreate(MetricBase):
    """Payload accepted when recording a new metric sample."""

    pass


class Metric(MetricBase):
    """Persisted representation of a metric sample."""

    id: UUID = Field(default_factory=uuid4)
    org_id: UUID
    recorded_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        from_attributes = True


class MetricResponse(BaseModel):
    data: Metric


class MetricListResponse(BaseModel):
    data: list[Metric]
    count: int
    pagination: PaginationMeta


class MetricSummary(BaseModel):
    name: str
    metric_type: MetricType
    count: int
    average: Optional[float]
    minimum: Optional[float]
    maximum: Optional[float]
    p50: Optional[float]
    p95: Optional[float]


class MetricSummaryResponse(BaseModel):
    data: MetricSummary


class SLOStatus(str, Enum):
    """Represents the health of a service level objective evaluation."""

    HEALTHY = "healthy"
    BREACHED = "breached"
    UNKNOWN = "unknown"


class SLOReport(BaseModel):
    """Response payload for evaluated service level objectives."""

    name: str
    target_value: float
    unit: str
    sample_count: int
    p95: Optional[float]
    status: SLOStatus


class SLOReportResponse(BaseModel):
    data: SLOReport


def compute_summary(name: str, metric_type: MetricType, samples: list[Metric]) -> MetricSummary:
    if not samples:
        return MetricSummary(
            name=name,
            metric_type=metric_type,
            count=0,
            average=None,
            minimum=None,
            maximum=None,
            p50=None,
            p95=None,
        )
    values = sorted(sample.value for sample in samples)
    count = len(values)
    average = sum(values) / count if count else None
    minimum = values[0]
    maximum = values[-1]

    def _percentile(data: list[float], percentile: float) -> float:
        if not data:
            raise ValueError("Cannot compute percentile of empty data")
        if len(data) == 1:
            return data[0]
        rank = percentile * (len(data) - 1)
        lower_index = floor(rank)
        upper_index = min(len(data) - 1, lower_index + 1)
        weight = rank - lower_index
        lower_value = data[lower_index]
        upper_value = data[upper_index]
        return lower_value + (upper_value - lower_value) * weight

    p50 = _percentile(values, 0.5)
    p95 = _percentile(values, 0.95)

    return MetricSummary(
        name=name,
        metric_type=metric_type,
        count=count,
        average=average,
        minimum=minimum,
        maximum=maximum,
        p50=p50,
        p95=p95,
    )
