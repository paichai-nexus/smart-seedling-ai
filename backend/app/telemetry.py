from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Iterable, Mapping, Optional


@dataclass(frozen=True)
class SensorMatch:
    reading_id: int
    time_delta_seconds: float


def nearest_sensor_reading(
    captured_at: datetime,
    readings: Iterable[Mapping],
    maximum_age_minutes: float,
) -> Optional[SensorMatch]:
    """Return the temporally closest reading within a symmetric time window."""
    if captured_at.tzinfo is None or captured_at.utcoffset() is None:
        raise ValueError("captured_at must include a timezone offset")
    if maximum_age_minutes < 0:
        raise ValueError("maximum_age_minutes must be non-negative")

    closest = None
    for reading in readings:
        measured_at = datetime.fromisoformat(str(reading["measured_at"]))
        if measured_at.tzinfo is None or measured_at.utcoffset() is None:
            continue
        delta = abs((captured_at - measured_at).total_seconds())
        candidate = SensorMatch(reading_id=int(reading["id"]), time_delta_seconds=delta)
        if closest is None or candidate.time_delta_seconds < closest.time_delta_seconds:
            closest = candidate

    if closest is None or closest.time_delta_seconds > maximum_age_minutes * 60:
        return None
    return closest
