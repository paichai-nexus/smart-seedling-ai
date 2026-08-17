from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field

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


class ImageAnalysisRead(BaseModel):
    seedling_id: str
    observation_id: int
    image_path: str
    leaf_area_cm2: float
    green_pixel_count: int
    coverage_ratio: float
    analysis_confidence: float
    status: HealthStatus


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


class TrayAnalysisRead(BaseModel):
    capture_id: int
    tray_code: str
    captured_at: datetime
    image_path: str
    cells: list[TrayCellAnalysis]
