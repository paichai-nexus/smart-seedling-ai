from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, field_validator, model_validator

from .domain import HealthStatus


class TrayCreate(BaseModel):
    code: str = Field(min_length=1, max_length=40, examples=["TRAY-A"])
    crop: str = Field(min_length=1, max_length=80, examples=["tomato"])
    rows: int = Field(ge=1, le=100)
    columns: int = Field(ge=1, le=100)


class ObservationCreate(BaseModel):
    tray_code: str
    row: int = Field(ge=1)
    column: int = Field(ge=1)
    captured_at: datetime
    leaf_area_cm2: float = Field(ge=0)
    discoloration_ratio: float = Field(default=0, ge=0, le=1)
    damage_ratio: float = Field(default=0, ge=0, le=1)
    confidence: float = Field(default=1, ge=0, le=1)
    temperature_c: Optional[float] = None
    humidity_percent: Optional[float] = Field(default=None, ge=0, le=100)
    soil_moisture_percent: Optional[float] = Field(default=None, ge=0, le=100)


class ObservationRead(ObservationCreate):
    id: int
    seedling_id: str
    status: HealthStatus
    growth_rate_percent: Optional[float]


class DashboardSummary(BaseModel):
    total_seedlings: int
    healthy: int
    warning: int
    expert_review: int
    latest_capture_at: Optional[datetime]


class CaptureQualityRead(BaseModel):
    accepted: bool
    blur_score: float
    mean_brightness: float
    dark_pixel_ratio: float
    bright_pixel_ratio: float
    reasons: list[str]


class ImageAnalysisRead(BaseModel):
    seedling_id: str
    observation_id: int
    image_path: str
    leaf_area_cm2: float
    green_pixel_count: int
    coverage_ratio: float
    analysis_confidence: float
    status: HealthStatus
    quality: CaptureQualityRead


class SeedlingLatest(BaseModel):
    seedling_id: str
    tray_code: str
    row: int
    column: int
    captured_at: datetime
    leaf_area_cm2: float
    status: HealthStatus


class SeedlingHistoryPoint(BaseModel):
    captured_at: datetime
    leaf_area_cm2: float
    growth_rate_percent: Optional[float]
    discoloration_ratio: float
    damage_ratio: float
    status: HealthStatus


class TrayCellAnalysis(BaseModel):
    row: int
    column: int
    seedling_id: str
    observation_id: int
    leaf_area_cm2: float
    coverage_ratio: float
    analysis_confidence: float
    status: HealthStatus


class TrayRectificationRead(BaseModel):
    applied: bool
    corners: list[list[float]]
    source_area_ratio: Optional[float]


class TrayAnalysisRead(BaseModel):
    capture_id: int
    tray_code: str
    captured_at: datetime
    image_path: str
    cells: list[TrayCellAnalysis]
    quality: CaptureQualityRead
    rectification: TrayRectificationRead


class SensorReadingCreate(BaseModel):
    measured_at: datetime
    source: str = Field(default="manual", min_length=1, max_length=80)
    temperature_c: Optional[float] = Field(default=None, ge=-40, le=85)
    humidity_percent: Optional[float] = Field(default=None, ge=0, le=100)
    soil_moisture_percent: Optional[float] = Field(default=None, ge=0, le=100)
    illuminance_lux: Optional[float] = Field(default=None, ge=0)
    ec_ms_cm: Optional[float] = Field(default=None, ge=0, le=20)
    ph: Optional[float] = Field(default=None, ge=0, le=14)

    @field_validator("measured_at")
    @classmethod
    def measured_at_requires_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("measured_at must include a timezone offset")
        return value

    @model_validator(mode="after")
    def require_measurement(self):
        has_measurement = any(
            value is not None
            for value in (
                self.temperature_c,
                self.humidity_percent,
                self.soil_moisture_percent,
                self.illuminance_lux,
                self.ec_ms_cm,
                self.ph,
            )
        )
        if not has_measurement:
            raise ValueError("at least one sensor measurement is required")
        return self


class SensorReadingRead(SensorReadingCreate):
    id: int
    tray_code: str
