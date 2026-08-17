from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, field_validator, model_validator

from .domain import ExperimentGroupKind, ExpertAssessment, HealthStatus, RuleStatus


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


class SensorContextRead(BaseModel):
    reading_id: int
    measured_at: datetime
    source: str
    time_delta_seconds: float
    temperature_c: Optional[float]
    pressure_hpa: Optional[float] = None
    humidity_percent: Optional[float]
    soil_moisture_percent: Optional[float]
    soil_moisture_raw_adc: Optional[int] = None
    soil_moisture_voltage_v: Optional[float] = None
    illuminance_lux: Optional[float]
    ec_ms_cm: Optional[float]
    ph: Optional[float]


class EffectiveCaptureSettingsRead(BaseModel):
    source: str
    pixels_per_cm: float
    margin_ratio: float
    rectify: bool
    minimum_tray_area_ratio: float
    maximum_sensor_age_minutes: float


class TrayAnalysisRead(BaseModel):
    capture_id: int
    tray_code: str
    captured_at: datetime
    image_path: str
    cells: list[TrayCellAnalysis]
    quality: CaptureQualityRead
    rectification: TrayRectificationRead
    sensor_context: Optional[SensorContextRead]
    capture_settings: EffectiveCaptureSettingsRead


class SensorReadingCreate(BaseModel):
    measured_at: datetime
    source: str = Field(default="manual", min_length=1, max_length=80)
    temperature_c: Optional[float] = Field(default=None, ge=-40, le=85)
    pressure_hpa: Optional[float] = Field(default=None, ge=300, le=1200)
    humidity_percent: Optional[float] = Field(default=None, ge=0, le=100)
    soil_moisture_percent: Optional[float] = Field(default=None, ge=0, le=100)
    soil_moisture_raw_adc: Optional[int] = Field(default=None, ge=0, le=32767)
    soil_moisture_voltage_v: Optional[float] = Field(default=None, ge=0, le=6.144)
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
                self.pressure_hpa,
                self.humidity_percent,
                self.soil_moisture_percent,
                self.soil_moisture_raw_adc,
                self.soil_moisture_voltage_v,
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


class ExpertReviewCreate(BaseModel):
    reviewer: str = Field(min_length=1, max_length=100)
    assessment: ExpertAssessment
    observable_notes: str = Field(min_length=1, max_length=2000)
    possible_cause_notes: Optional[str] = Field(default=None, max_length=2000)
    reviewed_at: datetime

    @field_validator("reviewed_at")
    @classmethod
    def reviewed_at_requires_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("reviewed_at must include a timezone offset")
        return value


class ExpertReviewRead(ExpertReviewCreate):
    id: int
    observation_id: int


class KnowledgeRuleCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    observable_signals: list[str] = Field(min_length=1)
    possible_causes: list[str] = Field(min_length=1)
    required_checks: list[str] = Field(min_length=1)
    suggested_actions: list[str] = Field(min_length=1)
    safety_note: str = Field(min_length=1, max_length=1000)
    created_by: str = Field(min_length=1, max_length=100)


class KnowledgeRuleRead(KnowledgeRuleCreate):
    id: int
    status: RuleStatus
    approved_by: Optional[str]
    approved_at: Optional[datetime]


class KnowledgeRuleApproval(BaseModel):
    approved_by: str = Field(min_length=1, max_length=100)
    approved_at: datetime

    @field_validator("approved_at")
    @classmethod
    def approved_at_requires_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("approved_at must include a timezone offset")
        return value


class ReviewQueueItem(BaseModel):
    observation_id: int
    seedling_id: str
    tray_code: str
    captured_at: datetime
    leaf_area_cm2: float
    discoloration_ratio: float
    damage_ratio: float
    confidence: float
    status: HealthStatus


class RecommendationRuleRead(BaseModel):
    rule_id: int
    title: str
    matched_signals: list[str]
    match_score: float
    possible_causes: list[str]
    required_checks: list[str]
    suggested_actions: list[str]
    safety_note: str
    approved_by: str


class ObservationRecommendationRead(BaseModel):
    observation_id: int
    observed_signals: list[str]
    rules: list[RecommendationRuleRead]
    disclaimer: str


class ExperimentGroupCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    kind: ExperimentGroupKind
    description: str = Field(min_length=1, max_length=1000)
    tray_codes: list[str] = Field(min_length=1)


class ExperimentCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    crop: str = Field(min_length=1, max_length=100)
    hypothesis: str = Field(min_length=1, max_length=2000)
    started_at: datetime
    ended_at: Optional[datetime] = None
    created_by: str = Field(min_length=1, max_length=100)
    groups: list[ExperimentGroupCreate] = Field(min_length=2)

    @model_validator(mode="after")
    def validate_experiment_design(self):
        for timestamp in (self.started_at, self.ended_at):
            if timestamp is not None and (
                timestamp.tzinfo is None or timestamp.utcoffset() is None
            ):
                raise ValueError("experiment timestamps must include a timezone offset")
        if self.ended_at is not None and self.ended_at <= self.started_at:
            raise ValueError("ended_at must be after started_at")
        kinds = {group.kind for group in self.groups}
        if ExperimentGroupKind.CONTROL not in kinds or ExperimentGroupKind.TREATMENT not in kinds:
            raise ValueError("an experiment requires control and treatment groups")
        tray_codes = [code.upper() for group in self.groups for code in group.tray_codes]
        if len(tray_codes) != len(set(tray_codes)):
            raise ValueError("a tray can belong to only one group in an experiment")
        return self


class ExperimentGroupRead(ExperimentGroupCreate):
    id: int


class ExperimentRead(BaseModel):
    id: int
    name: str
    crop: str
    hypothesis: str
    started_at: datetime
    ended_at: Optional[datetime]
    created_by: str
    groups: list[ExperimentGroupRead]


class ExperimentListItem(BaseModel):
    id: int
    name: str
    crop: str
    started_at: datetime
    ended_at: Optional[datetime]


class GrowthSampleRead(BaseModel):
    seedling_id: str
    initial_leaf_area_cm2: float
    final_leaf_area_cm2: float
    growth_rate_percent: float
    observation_count: int


class GroupGrowthSummaryRead(BaseModel):
    group_id: int
    group_name: str
    group_kind: ExperimentGroupKind
    sample_size: int
    mean_growth_rate_percent: float
    median_growth_rate_percent: float
    standard_deviation_percent: float
    minimum_growth_rate_percent: float
    maximum_growth_rate_percent: float
    samples: list[GrowthSampleRead]


class ExperimentComparisonRead(BaseModel):
    experiment_id: int
    experiment_name: str
    groups: list[GroupGrowthSummaryRead]
    interpretation_note: str


class CaptureProfileUpsert(BaseModel):
    pixels_per_cm: float = Field(gt=0)
    margin_ratio: float = Field(default=0.08, ge=0, lt=0.4)
    rectify: bool = False
    minimum_tray_area_ratio: float = Field(default=0.25, gt=0, lt=1)
    maximum_sensor_age_minutes: float = Field(default=30, ge=0, le=1440)
    updated_by: str = Field(min_length=1, max_length=100)
    updated_at: datetime

    @field_validator("updated_at")
    @classmethod
    def updated_at_requires_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("updated_at must include a timezone offset")
        return value


class CaptureProfileRead(CaptureProfileUpsert):
    tray_code: str
