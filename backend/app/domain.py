from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Optional


class HealthStatus(str, Enum):
    HEALTHY = "healthy"
    WARNING = "warning"
    EXPERT_REVIEW = "expert_review"


class ExpertAssessment(str, Enum):
    HEALTHY = "healthy"
    WARNING = "warning"
    ABNORMAL = "abnormal"
    UNCERTAIN = "uncertain"


class RuleStatus(str, Enum):
    DRAFT = "draft"
    APPROVED = "approved"
    RETIRED = "retired"


@dataclass(frozen=True)
class ObservationMetrics:
    leaf_area_cm2: float
    discoloration_ratio: float = 0.0
    damage_ratio: float = 0.0
    confidence: float = 1.0

    def __post_init__(self) -> None:
        if self.leaf_area_cm2 < 0:
            raise ValueError("leaf_area_cm2 must be non-negative")
        for name in ("discoloration_ratio", "damage_ratio", "confidence"):
            value = getattr(self, name)
            if not 0 <= value <= 1:
                raise ValueError(f"{name} must be between 0 and 1")


@dataclass(frozen=True)
class TimedObservation:
    captured_at: datetime
    metrics: ObservationMetrics


def stable_seedling_id(tray_id: str, row: int, column: int) -> str:
    """Create an ID independent of model tracking and camera frame order."""
    if not tray_id.strip():
        raise ValueError("tray_id is required")
    if row < 1 or column < 1:
        raise ValueError("row and column are one-based positive integers")
    return f"{tray_id.strip().upper()}-R{row:02d}C{column:02d}"


def growth_rate_percent(previous: float, current: float) -> Optional[float]:
    if previous <= 0:
        return None
    return round(((current - previous) / previous) * 100, 2)


def classify_status(
    current: ObservationMetrics,
    previous: Optional[ObservationMetrics] = None,
) -> HealthStatus:
    """Conservative triage rule; this is explicitly not a diagnosis."""
    if current.confidence < 0.6:
        return HealthStatus.EXPERT_REVIEW
    if current.discoloration_ratio >= 0.2 or current.damage_ratio >= 0.15:
        return HealthStatus.EXPERT_REVIEW

    growth = None
    if previous is not None:
        growth = growth_rate_percent(previous.leaf_area_cm2, current.leaf_area_cm2)
    if current.discoloration_ratio >= 0.08 or current.damage_ratio >= 0.05:
        return HealthStatus.WARNING
    if growth is not None and growth < 0:
        return HealthStatus.WARNING
    return HealthStatus.HEALTHY
