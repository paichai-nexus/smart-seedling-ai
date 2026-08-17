from __future__ import annotations

import csv
import io
import json
import os
from contextlib import asynccontextmanager
from datetime import datetime
from hashlib import sha256
from pathlib import Path
from typing import Optional
from uuid import uuid4

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, StreamingResponse
from typing_extensions import Annotated

from .domain import ObservationMetrics, classify_status, growth_rate_percent, stable_seedling_id
from .experiments import summarize_group_growth
from .recommendations import derive_observable_signals, rank_knowledge_rules
from .repository import Repository
from .schemas import (
    CaptureProfileRead,
    CaptureProfileUpsert,
    CaptureQualityRead,
    DashboardSummary,
    EffectiveCaptureSettingsRead,
    ExperimentComparisonRead,
    ExperimentCreate,
    ExperimentGroupRead,
    ExperimentListItem,
    ExperimentRead,
    ExpertReviewCreate,
    ExpertReviewRead,
    GroupGrowthSummaryRead,
    GrowthSampleRead,
    ImageAnalysisRead,
    KnowledgeRuleApproval,
    KnowledgeRuleCreate,
    KnowledgeRuleRead,
    ObservationCreate,
    ObservationRead,
    ObservationRecommendationRead,
    RecommendationRuleRead,
    ReviewQueueItem,
    SeedlingHistoryPoint,
    SeedlingLatest,
    SensorContextRead,
    SensorReadingCreate,
    SensorReadingRead,
    SoilCalibrationCreate,
    SoilCalibrationRead,
    TrayAnalysisRead,
    TrayCellAnalysis,
    TrayCreate,
    TrayRectificationRead,
)
from .soil_calibration import relative_soil_moisture
from .telemetry import nearest_sensor_reading
from .vision import (
    analyze_green_leaf_area,
    assess_capture_quality,
    decode_image,
    detect_and_rectify_tray,
    split_tray_grid,
)

ROOT = Path(__file__).resolve().parents[2]
repository = Repository(os.getenv("SMART_SEEDLING_DB", str(ROOT / "smart_seedling.db")))
UPLOAD_ROOT = Path(os.getenv("SMART_SEEDLING_UPLOADS", str(ROOT / "uploads")))
MAX_IMAGE_BYTES = 10 * 1024 * 1024


def quality_response(quality) -> CaptureQualityRead:
    return CaptureQualityRead(
        accepted=quality.accepted,
        blur_score=quality.blur_score,
        mean_brightness=quality.mean_brightness,
        dark_pixel_ratio=quality.dark_pixel_ratio,
        bright_pixel_ratio=quality.bright_pixel_ratio,
        reasons=list(quality.reasons),
    )


@asynccontextmanager
async def lifespan(_: FastAPI):
    repository.initialize()
    UPLOAD_ROOT.mkdir(parents=True, exist_ok=True)
    yield


app = FastAPI(
    title="Smart Seedling AI",
    version="0.1.0",
    description="Observation and research API. Results are not biological diagnoses.",
    lifespan=lifespan,
)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/dashboard", include_in_schema=False)
def dashboard() -> FileResponse:
    return FileResponse(ROOT / "frontend" / "index.html")


@app.post("/api/v1/trays", status_code=201)
def create_tray(payload: TrayCreate) -> dict[str, str]:
    with repository.connect() as connection:
        try:
            connection.execute(
                "INSERT INTO trays(code, crop, rows, columns) VALUES (?, ?, ?, ?)",
                (payload.code.upper(), payload.crop, payload.rows, payload.columns),
            )
        except Exception as exc:
            raise HTTPException(status_code=409, detail="Tray already exists") from exc
    return {"code": payload.code.upper()}


@app.put(
    "/api/v1/trays/{tray_code}/capture-profile",
    response_model=CaptureProfileRead,
)
def upsert_capture_profile(
    tray_code: str,
    payload: CaptureProfileUpsert,
) -> CaptureProfileRead:
    tray_code = tray_code.upper()
    with repository.connect() as connection:
        tray = connection.execute("SELECT 1 FROM trays WHERE code = ?", (tray_code,)).fetchone()
        if tray is None:
            raise HTTPException(status_code=404, detail="Tray not found")
        connection.execute(
            """INSERT INTO capture_profiles(
                   tray_code, pixels_per_cm, margin_ratio, rectify,
                   minimum_tray_area_ratio, maximum_sensor_age_minutes,
                   updated_by, updated_at
               ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(tray_code) DO UPDATE SET
                   pixels_per_cm = excluded.pixels_per_cm,
                   margin_ratio = excluded.margin_ratio,
                   rectify = excluded.rectify,
                   minimum_tray_area_ratio = excluded.minimum_tray_area_ratio,
                   maximum_sensor_age_minutes = excluded.maximum_sensor_age_minutes,
                   updated_by = excluded.updated_by,
                   updated_at = excluded.updated_at""",
            (
                tray_code,
                payload.pixels_per_cm,
                payload.margin_ratio,
                int(payload.rectify),
                payload.minimum_tray_area_ratio,
                payload.maximum_sensor_age_minutes,
                payload.updated_by,
                payload.updated_at.isoformat(),
            ),
        )
    return CaptureProfileRead(tray_code=tray_code, **payload.model_dump())


@app.get(
    "/api/v1/trays/{tray_code}/capture-profile",
    response_model=CaptureProfileRead,
)
def get_capture_profile(tray_code: str) -> CaptureProfileRead:
    with repository.connect() as connection:
        row = connection.execute(
            "SELECT * FROM capture_profiles WHERE tray_code = ?", (tray_code.upper(),)
        ).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Capture profile not found")
    values = dict(row)
    values["rectify"] = bool(values["rectify"])
    return CaptureProfileRead(**values)


@app.post("/api/v1/observations", response_model=ObservationRead, status_code=201)
def create_observation(payload: ObservationCreate) -> ObservationRead:
    tray_code = payload.tray_code.upper()
    seedling_id = stable_seedling_id(tray_code, payload.row, payload.column)
    current = ObservationMetrics(
        leaf_area_cm2=payload.leaf_area_cm2,
        discoloration_ratio=payload.discoloration_ratio,
        damage_ratio=payload.damage_ratio,
        confidence=payload.confidence,
    )
    with repository.connect() as connection:
        tray = connection.execute(
            "SELECT rows, columns FROM trays WHERE code = ?", (tray_code,)
        ).fetchone()
        if tray is None:
            raise HTTPException(status_code=404, detail="Tray not found")
        if payload.row > tray["rows"] or payload.column > tray["columns"]:
            raise HTTPException(status_code=422, detail="Cell is outside tray geometry")

        prior = connection.execute(
            """SELECT leaf_area_cm2, discoloration_ratio, damage_ratio, confidence
               FROM observations WHERE seedling_id = ? AND captured_at < ?
               ORDER BY captured_at DESC LIMIT 1""",
            (seedling_id, payload.captured_at.isoformat()),
        ).fetchone()
        previous = ObservationMetrics(**dict(prior)) if prior else None
        status = classify_status(current, previous)
        growth = (
            growth_rate_percent(previous.leaf_area_cm2, current.leaf_area_cm2) if previous else None
        )
        try:
            cursor = connection.execute(
                """INSERT INTO observations(
                    seedling_id, tray_code, cell_row, cell_column, captured_at,
                    leaf_area_cm2, discoloration_ratio, damage_ratio, confidence, status,
                    temperature_c, humidity_percent, soil_moisture_percent
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    seedling_id,
                    tray_code,
                    payload.row,
                    payload.column,
                    payload.captured_at.isoformat(),
                    payload.leaf_area_cm2,
                    payload.discoloration_ratio,
                    payload.damage_ratio,
                    payload.confidence,
                    status.value,
                    payload.temperature_c,
                    payload.humidity_percent,
                    payload.soil_moisture_percent,
                ),
            )
        except Exception as exc:
            raise HTTPException(status_code=409, detail="Observation already exists") from exc
    return ObservationRead(
        id=cursor.lastrowid,
        seedling_id=seedling_id,
        status=status,
        growth_rate_percent=growth,
        **payload.model_dump(),
    )


@app.post("/api/v1/images/analyze", response_model=ImageAnalysisRead, status_code=201)
async def analyze_image(
    image: Annotated[UploadFile, File()],
    tray_code: Annotated[str, Form()],
    row: Annotated[int, Form(ge=1)],
    column: Annotated[int, Form(ge=1)],
    captured_at: Annotated[datetime, Form()],
    pixels_per_cm: Annotated[float, Form(gt=0)],
) -> ImageAnalysisRead:
    if image.content_type not in {"image/jpeg", "image/png"}:
        raise HTTPException(status_code=415, detail="Only JPEG and PNG images are supported")
    content = await image.read(MAX_IMAGE_BYTES + 1)
    if len(content) > MAX_IMAGE_BYTES:
        raise HTTPException(status_code=413, detail="Image exceeds the 10 MB limit")
    try:
        decoded = decode_image(content)
        quality = assess_capture_quality(decoded)
        if not quality.accepted:
            raise HTTPException(
                status_code=422,
                detail={
                    "message": "Capture quality gate failed",
                    "quality": quality_response(quality).model_dump(),
                },
            )
        analysis = analyze_green_leaf_area(decoded, pixels_per_cm)
    except HTTPException:
        raise
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    observation = create_observation(
        ObservationCreate(
            tray_code=tray_code,
            row=row,
            column=column,
            captured_at=captured_at,
            leaf_area_cm2=analysis.leaf_area_cm2,
            confidence=analysis.confidence,
        )
    )
    extension = ".png" if image.content_type == "image/png" else ".jpg"
    relative_path = f"{tray_code.upper()}/{captured_at.date().isoformat()}/{uuid4().hex}{extension}"
    destination = UPLOAD_ROOT / relative_path
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(content)
    with repository.connect() as connection:
        connection.execute(
            """INSERT INTO image_assets(observation_id, relative_path, sha256, mime_type)
               VALUES (?, ?, ?, ?)""",
            (observation.id, relative_path, sha256(content).hexdigest(), image.content_type),
        )
    return ImageAnalysisRead(
        seedling_id=observation.seedling_id,
        observation_id=observation.id,
        image_path=relative_path,
        leaf_area_cm2=analysis.leaf_area_cm2,
        green_pixel_count=analysis.green_pixel_count,
        coverage_ratio=analysis.coverage_ratio,
        analysis_confidence=analysis.confidence,
        status=observation.status,
        quality=quality_response(quality),
    )


@app.post(
    "/api/v1/trays/{tray_code}/images/analyze",
    response_model=TrayAnalysisRead,
    status_code=201,
)
async def analyze_tray_image(
    tray_code: str,
    image: Annotated[UploadFile, File()],
    captured_at: Annotated[datetime, Form()],
    pixels_per_cm: Annotated[Optional[float], Form(gt=0)] = None,
    margin_ratio: Annotated[Optional[float], Form(ge=0, lt=0.4)] = None,
    rectify: Annotated[Optional[bool], Form()] = None,
    minimum_tray_area_ratio: Annotated[Optional[float], Form(gt=0, lt=1)] = None,
    maximum_sensor_age_minutes: Annotated[Optional[float], Form(ge=0, le=1440)] = None,
) -> TrayAnalysisRead:
    tray_code = tray_code.upper()
    if captured_at.tzinfo is None or captured_at.utcoffset() is None:
        raise HTTPException(status_code=422, detail="captured_at must include a timezone offset")
    if image.content_type not in {"image/jpeg", "image/png"}:
        raise HTTPException(status_code=415, detail="Only JPEG and PNG images are supported")
    content = await image.read(MAX_IMAGE_BYTES + 1)
    if len(content) > MAX_IMAGE_BYTES:
        raise HTTPException(status_code=413, detail="Image exceeds the 10 MB limit")
    with repository.connect() as connection:
        tray = connection.execute(
            "SELECT rows, columns FROM trays WHERE code = ?", (tray_code,)
        ).fetchone()
        profile = connection.execute(
            "SELECT * FROM capture_profiles WHERE tray_code = ?", (tray_code,)
        ).fetchone()
        sensor_rows = connection.execute(
            """SELECT id, measured_at, source, sensor_id, temperature_c, pressure_hpa,
                      humidity_percent, soil_moisture_percent, soil_moisture_raw_adc,
                      soil_moisture_voltage_v, soil_calibration_id,
                      soil_moisture_out_of_range, illuminance_lux, ec_ms_cm, ph
               FROM sensor_readings WHERE tray_code = ?
               ORDER BY measured_at DESC LIMIT 5000""",
            (tray_code,),
        ).fetchall()
    if tray is None:
        raise HTTPException(status_code=404, detail="Tray not found")
    if pixels_per_cm is None and profile is None:
        raise HTTPException(
            status_code=422,
            detail="pixels_per_cm is required when no capture profile exists",
        )
    effective_pixels_per_cm = (
        pixels_per_cm if pixels_per_cm is not None else profile["pixels_per_cm"]
    )
    effective_margin_ratio = (
        margin_ratio if margin_ratio is not None else profile["margin_ratio"] if profile else 0.08
    )
    effective_rectify = (
        rectify if rectify is not None else bool(profile["rectify"]) if profile else False
    )
    effective_minimum_tray_area = (
        minimum_tray_area_ratio
        if minimum_tray_area_ratio is not None
        else profile["minimum_tray_area_ratio"]
        if profile
        else 0.25
    )
    effective_maximum_sensor_age = (
        maximum_sensor_age_minutes
        if maximum_sensor_age_minutes is not None
        else profile["maximum_sensor_age_minutes"]
        if profile
        else 30
    )
    sensor_match = nearest_sensor_reading(
        captured_at,
        sensor_rows,
        maximum_age_minutes=effective_maximum_sensor_age,
    )
    matched_sensor = (
        next(row for row in sensor_rows if row["id"] == sensor_match.reading_id)
        if sensor_match
        else None
    )

    try:
        decoded = decode_image(content)
        quality = assess_capture_quality(decoded)
        if not quality.accepted:
            raise HTTPException(
                status_code=422,
                detail={
                    "message": "Capture quality gate failed",
                    "quality": quality_response(quality).model_dump(),
                },
            )
        if effective_rectify:
            rectification = detect_and_rectify_tray(decoded, effective_minimum_tray_area)
            analysis_image = rectification.image
        else:
            rectification = None
            analysis_image = decoded
        cells = split_tray_grid(
            analysis_image,
            tray["rows"],
            tray["columns"],
            effective_margin_ratio,
        )
    except HTTPException:
        raise
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    results = []
    for cell in cells:
        analysis = analyze_green_leaf_area(cell.image, effective_pixels_per_cm)
        observation = create_observation(
            ObservationCreate(
                tray_code=tray_code,
                row=cell.row,
                column=cell.column,
                captured_at=captured_at,
                leaf_area_cm2=analysis.leaf_area_cm2,
                confidence=analysis.confidence,
            )
        )
        results.append((observation, analysis))

    extension = ".png" if image.content_type == "image/png" else ".jpg"
    relative_path = f"{tray_code}/{captured_at.date().isoformat()}/tray-{uuid4().hex}{extension}"
    destination = UPLOAD_ROOT / relative_path
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(content)
    try:
        with repository.connect() as connection:
            cursor = connection.execute(
                """INSERT INTO tray_captures(
                       tray_code, captured_at, relative_path, sha256, mime_type, pixels_per_cm
                   ) VALUES (?, ?, ?, ?, ?, ?)""",
                (
                    tray_code,
                    captured_at.isoformat(),
                    relative_path,
                    sha256(content).hexdigest(),
                    image.content_type,
                    effective_pixels_per_cm,
                ),
            )
            capture_id = cursor.lastrowid
            connection.executemany(
                "INSERT INTO capture_observations(capture_id, observation_id) VALUES (?, ?)",
                [(capture_id, observation.id) for observation, _ in results],
            )
            if sensor_match:
                connection.execute(
                    """INSERT INTO capture_sensor_links(
                           capture_id, sensor_reading_id, time_delta_seconds
                       ) VALUES (?, ?, ?)""",
                    (capture_id, sensor_match.reading_id, sensor_match.time_delta_seconds),
                )
    except Exception as exc:
        destination.unlink(missing_ok=True)
        raise HTTPException(status_code=409, detail="Tray capture already exists") from exc

    return TrayAnalysisRead(
        capture_id=capture_id,
        tray_code=tray_code,
        captured_at=captured_at,
        image_path=relative_path,
        quality=quality_response(quality),
        rectification=TrayRectificationRead(
            applied=rectification is not None,
            corners=[list(point) for point in rectification.corners] if rectification else [],
            source_area_ratio=rectification.source_area_ratio if rectification else None,
        ),
        sensor_context=(
            SensorContextRead(
                reading_id=matched_sensor["id"],
                measured_at=matched_sensor["measured_at"],
                source=matched_sensor["source"],
                sensor_id=matched_sensor["sensor_id"],
                time_delta_seconds=sensor_match.time_delta_seconds,
                temperature_c=matched_sensor["temperature_c"],
                pressure_hpa=matched_sensor["pressure_hpa"],
                humidity_percent=matched_sensor["humidity_percent"],
                soil_moisture_percent=matched_sensor["soil_moisture_percent"],
                soil_moisture_raw_adc=matched_sensor["soil_moisture_raw_adc"],
                soil_moisture_voltage_v=matched_sensor["soil_moisture_voltage_v"],
                soil_calibration_id=matched_sensor["soil_calibration_id"],
                soil_moisture_out_of_range=(
                    bool(matched_sensor["soil_moisture_out_of_range"])
                    if matched_sensor["soil_moisture_out_of_range"] is not None
                    else None
                ),
                illuminance_lux=matched_sensor["illuminance_lux"],
                ec_ms_cm=matched_sensor["ec_ms_cm"],
                ph=matched_sensor["ph"],
            )
            if matched_sensor and sensor_match
            else None
        ),
        capture_settings=EffectiveCaptureSettingsRead(
            source=(
                "profile_with_request_overrides"
                if profile
                and any(
                    value is not None
                    for value in (
                        pixels_per_cm,
                        margin_ratio,
                        rectify,
                        minimum_tray_area_ratio,
                        maximum_sensor_age_minutes,
                    )
                )
                else "profile"
                if profile
                else "request"
            ),
            pixels_per_cm=effective_pixels_per_cm,
            margin_ratio=effective_margin_ratio,
            rectify=effective_rectify,
            minimum_tray_area_ratio=effective_minimum_tray_area,
            maximum_sensor_age_minutes=effective_maximum_sensor_age,
        ),
        cells=[
            TrayCellAnalysis(
                row=observation.row,
                column=observation.column,
                seedling_id=observation.seedling_id,
                observation_id=observation.id,
                leaf_area_cm2=analysis.leaf_area_cm2,
                coverage_ratio=analysis.coverage_ratio,
                analysis_confidence=analysis.confidence,
                status=observation.status,
            )
            for observation, analysis in results
        ],
    )


@app.get("/api/v1/summary", response_model=DashboardSummary)
def summary() -> DashboardSummary:
    query = """
    WITH latest AS (
      SELECT *, ROW_NUMBER() OVER (PARTITION BY seedling_id ORDER BY captured_at DESC) AS rank
      FROM observations
    )
    SELECT COUNT(*) AS total,
           SUM(status = 'healthy') AS healthy,
           SUM(status = 'warning') AS warning,
           SUM(status = 'expert_review') AS expert_review,
           MAX(captured_at) AS latest_capture_at
    FROM latest WHERE rank = 1
    """
    with repository.connect() as connection:
        row = connection.execute(query).fetchone()
    return DashboardSummary(
        total_seedlings=row["total"] or 0,
        healthy=row["healthy"] or 0,
        warning=row["warning"] or 0,
        expert_review=row["expert_review"] or 0,
        latest_capture_at=row["latest_capture_at"],
    )


@app.get("/api/v1/seedlings", response_model=list[SeedlingLatest])
def list_seedlings() -> list[SeedlingLatest]:
    query = """
    WITH latest AS (
      SELECT *, ROW_NUMBER() OVER (PARTITION BY seedling_id ORDER BY captured_at DESC) AS rank
      FROM observations
    )
    SELECT seedling_id, tray_code, cell_row, cell_column, captured_at, leaf_area_cm2, status
    FROM latest WHERE rank = 1 ORDER BY tray_code, cell_row, cell_column
    """
    with repository.connect() as connection:
        rows = connection.execute(query).fetchall()
    return [
        SeedlingLatest(
            seedling_id=row["seedling_id"],
            tray_code=row["tray_code"],
            row=row["cell_row"],
            column=row["cell_column"],
            captured_at=row["captured_at"],
            leaf_area_cm2=row["leaf_area_cm2"],
            status=row["status"],
        )
        for row in rows
    ]


@app.get(
    "/api/v1/seedlings/{seedling_id}/history",
    response_model=list[SeedlingHistoryPoint],
)
def seedling_history(seedling_id: str, limit: int = 100) -> list[SeedlingHistoryPoint]:
    if not 1 <= limit <= 500:
        raise HTTPException(status_code=422, detail="limit must be between 1 and 500")
    query = """
    SELECT captured_at, leaf_area_cm2, discoloration_ratio, damage_ratio, status
    FROM observations WHERE seedling_id = ? ORDER BY captured_at ASC LIMIT ?
    """
    with repository.connect() as connection:
        rows = connection.execute(query, (seedling_id.upper(), limit)).fetchall()
    if not rows:
        raise HTTPException(status_code=404, detail="Seedling not found")

    points = []
    previous_area = None
    for row in rows:
        growth = (
            growth_rate_percent(previous_area, row["leaf_area_cm2"])
            if previous_area is not None
            else None
        )
        points.append(
            SeedlingHistoryPoint(
                captured_at=row["captured_at"],
                leaf_area_cm2=row["leaf_area_cm2"],
                growth_rate_percent=growth,
                discoloration_ratio=row["discoloration_ratio"],
                damage_ratio=row["damage_ratio"],
                status=row["status"],
            )
        )
        previous_area = row["leaf_area_cm2"]
    return points


@app.post(
    "/api/v1/trays/{tray_code}/soil-calibrations",
    response_model=SoilCalibrationRead,
    status_code=201,
)
def create_soil_calibration(
    tray_code: str,
    payload: SoilCalibrationCreate,
) -> SoilCalibrationRead:
    tray_code = tray_code.upper()
    with repository.connect() as connection:
        tray = connection.execute("SELECT 1 FROM trays WHERE code = ?", (tray_code,)).fetchone()
        if tray is None:
            raise HTTPException(status_code=404, detail="Tray not found")
        connection.execute(
            """UPDATE soil_calibrations SET active = 0
               WHERE tray_code = ? AND source = ? AND sensor_id = ? AND active = 1""",
            (tray_code, payload.source, payload.sensor_id),
        )
        cursor = connection.execute(
            """INSERT INTO soil_calibrations(
                   tray_code, source, sensor_id, dry_adc, wet_adc, calibrated_at,
                   calibrated_by, method_notes, active
               ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1)""",
            (
                tray_code,
                payload.source,
                payload.sensor_id,
                payload.dry_adc,
                payload.wet_adc,
                payload.calibrated_at.isoformat(),
                payload.calibrated_by,
                payload.method_notes,
            ),
        )
    return SoilCalibrationRead(
        id=cursor.lastrowid,
        tray_code=tray_code,
        active=True,
        **payload.model_dump(),
    )


@app.get(
    "/api/v1/trays/{tray_code}/soil-calibrations",
    response_model=list[SoilCalibrationRead],
)
def list_soil_calibrations(tray_code: str, active_only: bool = True) -> list[SoilCalibrationRead]:
    where = "AND active = 1" if active_only else ""
    with repository.connect() as connection:
        rows = connection.execute(
            f"""SELECT id, tray_code, source, sensor_id, dry_adc, wet_adc,
                       calibrated_at, calibrated_by, method_notes, active
                FROM soil_calibrations WHERE tray_code = ? {where}
                ORDER BY calibrated_at DESC""",
            (tray_code.upper(),),
        ).fetchall()
    return [SoilCalibrationRead(**{**dict(row), "active": bool(row["active"])}) for row in rows]


@app.post(
    "/api/v1/trays/{tray_code}/sensor-readings",
    response_model=SensorReadingRead,
    status_code=201,
)
def create_sensor_reading(tray_code: str, payload: SensorReadingCreate) -> SensorReadingRead:
    tray_code = tray_code.upper()
    with repository.connect() as connection:
        tray = connection.execute("SELECT 1 FROM trays WHERE code = ?", (tray_code,)).fetchone()
        if tray is None:
            raise HTTPException(status_code=404, detail="Tray not found")
        calibration = None
        if payload.soil_moisture_raw_adc is not None and payload.sensor_id:
            calibration = connection.execute(
                """SELECT id, dry_adc, wet_adc FROM soil_calibrations
                   WHERE tray_code = ? AND source = ? AND sensor_id = ? AND active = 1""",
                (tray_code, payload.source, payload.sensor_id),
            ).fetchone()
        moisture_percent = payload.soil_moisture_percent
        calibration_id = None
        out_of_range = None
        if calibration:
            estimate = relative_soil_moisture(
                payload.soil_moisture_raw_adc,
                calibration["dry_adc"],
                calibration["wet_adc"],
            )
            moisture_percent = estimate.relative_percent
            calibration_id = calibration["id"]
            out_of_range = estimate.out_of_calibration_range
        try:
            cursor = connection.execute(
                """INSERT INTO sensor_readings(
                       tray_code, measured_at, source, sensor_id, temperature_c, pressure_hpa,
                       humidity_percent, soil_moisture_percent, soil_moisture_raw_adc,
                       soil_moisture_voltage_v, soil_calibration_id,
                       soil_moisture_out_of_range, illuminance_lux, ec_ms_cm, ph
                   ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    tray_code,
                    payload.measured_at.isoformat(),
                    payload.source,
                    payload.sensor_id,
                    payload.temperature_c,
                    payload.pressure_hpa,
                    payload.humidity_percent,
                    moisture_percent,
                    payload.soil_moisture_raw_adc,
                    payload.soil_moisture_voltage_v,
                    calibration_id,
                    int(out_of_range) if out_of_range is not None else None,
                    payload.illuminance_lux,
                    payload.ec_ms_cm,
                    payload.ph,
                ),
            )
        except Exception as exc:
            raise HTTPException(status_code=409, detail="Sensor reading already exists") from exc
    values = payload.model_dump()
    values.update(
        soil_moisture_percent=moisture_percent,
        soil_calibration_id=calibration_id,
        soil_moisture_out_of_range=out_of_range,
    )
    return SensorReadingRead(id=cursor.lastrowid, tray_code=tray_code, **values)


@app.get(
    "/api/v1/trays/{tray_code}/sensor-readings",
    response_model=list[SensorReadingRead],
)
def list_sensor_readings(tray_code: str, limit: int = 100) -> list[SensorReadingRead]:
    if not 1 <= limit <= 1000:
        raise HTTPException(status_code=422, detail="limit must be between 1 and 1000")
    tray_code = tray_code.upper()
    with repository.connect() as connection:
        tray = connection.execute("SELECT 1 FROM trays WHERE code = ?", (tray_code,)).fetchone()
        if tray is None:
            raise HTTPException(status_code=404, detail="Tray not found")
        rows = connection.execute(
            """SELECT id, tray_code, measured_at, source, sensor_id, temperature_c, pressure_hpa,
                      humidity_percent, soil_moisture_percent, soil_moisture_raw_adc,
                      soil_moisture_voltage_v, soil_calibration_id,
                      soil_moisture_out_of_range, illuminance_lux, ec_ms_cm, ph
               FROM sensor_readings WHERE tray_code = ?
               ORDER BY measured_at DESC LIMIT ?""",
            (tray_code, limit),
        ).fetchall()
    return [SensorReadingRead(**dict(row)) for row in rows]


@app.get("/api/v1/reviews/queue", response_model=list[ReviewQueueItem])
def review_queue(limit: int = 100) -> list[ReviewQueueItem]:
    if not 1 <= limit <= 500:
        raise HTTPException(status_code=422, detail="limit must be between 1 and 500")
    query = """
    WITH latest AS (
      SELECT *, ROW_NUMBER() OVER (PARTITION BY seedling_id ORDER BY captured_at DESC) AS rank
      FROM observations
    )
    SELECT id AS observation_id, seedling_id, tray_code, captured_at, leaf_area_cm2,
           discoloration_ratio, damage_ratio, confidence, status
    FROM latest
    WHERE rank = 1 AND status IN ('warning', 'expert_review')
      AND NOT EXISTS (SELECT 1 FROM expert_reviews WHERE observation_id = latest.id)
    ORDER BY captured_at ASC LIMIT ?
    """
    with repository.connect() as connection:
        rows = connection.execute(query, (limit,)).fetchall()
    return [ReviewQueueItem(**dict(row)) for row in rows]


@app.post(
    "/api/v1/observations/{observation_id}/reviews",
    response_model=ExpertReviewRead,
    status_code=201,
)
def create_expert_review(
    observation_id: int,
    payload: ExpertReviewCreate,
) -> ExpertReviewRead:
    with repository.connect() as connection:
        observation = connection.execute(
            "SELECT 1 FROM observations WHERE id = ?", (observation_id,)
        ).fetchone()
        if observation is None:
            raise HTTPException(status_code=404, detail="Observation not found")
        try:
            cursor = connection.execute(
                """INSERT INTO expert_reviews(
                       observation_id, reviewer, assessment, observable_notes,
                       possible_cause_notes, reviewed_at
                   ) VALUES (?, ?, ?, ?, ?, ?)""",
                (
                    observation_id,
                    payload.reviewer,
                    payload.assessment.value,
                    payload.observable_notes,
                    payload.possible_cause_notes,
                    payload.reviewed_at.isoformat(),
                ),
            )
        except Exception as exc:
            raise HTTPException(status_code=409, detail="Expert review already exists") from exc
    return ExpertReviewRead(
        id=cursor.lastrowid,
        observation_id=observation_id,
        **payload.model_dump(),
    )


def knowledge_rule_from_row(row) -> KnowledgeRuleRead:
    return KnowledgeRuleRead(
        id=row["id"],
        title=row["title"],
        observable_signals=json.loads(row["observable_signals_json"]),
        possible_causes=json.loads(row["possible_causes_json"]),
        required_checks=json.loads(row["required_checks_json"]),
        suggested_actions=json.loads(row["suggested_actions_json"]),
        safety_note=row["safety_note"],
        status=row["status"],
        created_by=row["created_by"],
        approved_by=row["approved_by"],
        approved_at=row["approved_at"],
    )


@app.post("/api/v1/knowledge-rules", response_model=KnowledgeRuleRead, status_code=201)
def create_knowledge_rule(payload: KnowledgeRuleCreate) -> KnowledgeRuleRead:
    with repository.connect() as connection:
        cursor = connection.execute(
            """INSERT INTO knowledge_rules(
                   title, observable_signals_json, possible_causes_json, required_checks_json,
                   suggested_actions_json, safety_note, status, created_by
               ) VALUES (?, ?, ?, ?, ?, ?, 'draft', ?)""",
            (
                payload.title,
                json.dumps(payload.observable_signals, ensure_ascii=False),
                json.dumps(payload.possible_causes, ensure_ascii=False),
                json.dumps(payload.required_checks, ensure_ascii=False),
                json.dumps(payload.suggested_actions, ensure_ascii=False),
                payload.safety_note,
                payload.created_by,
            ),
        )
        row = connection.execute(
            "SELECT * FROM knowledge_rules WHERE id = ?", (cursor.lastrowid,)
        ).fetchone()
    return knowledge_rule_from_row(row)


@app.post(
    "/api/v1/knowledge-rules/{rule_id}/approve",
    response_model=KnowledgeRuleRead,
)
def approve_knowledge_rule(
    rule_id: int,
    payload: KnowledgeRuleApproval,
) -> KnowledgeRuleRead:
    with repository.connect() as connection:
        cursor = connection.execute(
            """UPDATE knowledge_rules SET status = 'approved', approved_by = ?, approved_at = ?
               WHERE id = ? AND status = 'draft'""",
            (payload.approved_by, payload.approved_at.isoformat(), rule_id),
        )
        if cursor.rowcount == 0:
            raise HTTPException(status_code=409, detail="Rule is missing or not a draft")
        row = connection.execute(
            "SELECT * FROM knowledge_rules WHERE id = ?", (rule_id,)
        ).fetchone()
    return knowledge_rule_from_row(row)


@app.get("/api/v1/knowledge-rules", response_model=list[KnowledgeRuleRead])
def list_knowledge_rules(include_drafts: bool = False) -> list[KnowledgeRuleRead]:
    where = "status != 'retired'" if include_drafts else "status = 'approved'"
    with repository.connect() as connection:
        rows = connection.execute(
            f"SELECT * FROM knowledge_rules WHERE {where} ORDER BY id DESC"
        ).fetchall()
    return [knowledge_rule_from_row(row) for row in rows]


@app.get(
    "/api/v1/observations/{observation_id}/recommendations",
    response_model=ObservationRecommendationRead,
)
def observation_recommendations(observation_id: int) -> ObservationRecommendationRead:
    with repository.connect() as connection:
        observation = connection.execute(
            """SELECT id, seedling_id, captured_at, leaf_area_cm2, discoloration_ratio,
                      damage_ratio, confidence
               FROM observations WHERE id = ?""",
            (observation_id,),
        ).fetchone()
        if observation is None:
            raise HTTPException(status_code=404, detail="Observation not found")
        previous = connection.execute(
            """SELECT leaf_area_cm2 FROM observations
               WHERE seedling_id = ? AND captured_at < ?
               ORDER BY captured_at DESC LIMIT 1""",
            (observation["seedling_id"], observation["captured_at"]),
        ).fetchone()
        rule_rows = connection.execute(
            "SELECT * FROM knowledge_rules WHERE status = 'approved' ORDER BY id"
        ).fetchall()

    growth = (
        growth_rate_percent(previous["leaf_area_cm2"], observation["leaf_area_cm2"])
        if previous
        else None
    )
    signals = derive_observable_signals(
        discoloration_ratio=observation["discoloration_ratio"],
        damage_ratio=observation["damage_ratio"],
        confidence=observation["confidence"],
        growth_rate_percent=growth,
    )
    candidates = rank_knowledge_rules(
        signals,
        [(row["id"], json.loads(row["observable_signals_json"])) for row in rule_rows],
    )
    rows_by_id = {row["id"]: row for row in rule_rows}
    recommendations = []
    for candidate in candidates:
        row = rows_by_id[candidate.rule_id]
        recommendations.append(
            RecommendationRuleRead(
                rule_id=row["id"],
                title=row["title"],
                matched_signals=list(candidate.matched_signals),
                match_score=candidate.match_score,
                possible_causes=json.loads(row["possible_causes_json"]),
                required_checks=json.loads(row["required_checks_json"]),
                suggested_actions=json.loads(row["suggested_actions_json"]),
                safety_note=row["safety_note"],
                approved_by=row["approved_by"],
            )
        )
    return ObservationRecommendationRead(
        observation_id=observation_id,
        observed_signals=sorted(signals),
        rules=recommendations,
        disclaimer=(
            "These are expert-approved decision-support rules, not a diagnosis. "
            "Verify required checks before changing irrigation, fertilizer, or pesticide use."
        ),
    )


@app.post("/api/v1/experiments", response_model=ExperimentRead, status_code=201)
def create_experiment(payload: ExperimentCreate) -> ExperimentRead:
    tray_codes = [code.upper() for group in payload.groups for code in group.tray_codes]
    with repository.connect() as connection:
        placeholders = ",".join("?" for _ in tray_codes)
        existing = {
            row["code"]
            for row in connection.execute(
                f"SELECT code FROM trays WHERE code IN ({placeholders})", tray_codes
            ).fetchall()
        }
        missing = sorted(set(tray_codes) - existing)
        if missing:
            raise HTTPException(status_code=422, detail={"missing_trays": missing})

        cursor = connection.execute(
            """INSERT INTO experiments(
                   name, crop, hypothesis, started_at, ended_at, created_by
               ) VALUES (?, ?, ?, ?, ?, ?)""",
            (
                payload.name,
                payload.crop,
                payload.hypothesis,
                payload.started_at.isoformat(),
                payload.ended_at.isoformat() if payload.ended_at else None,
                payload.created_by,
            ),
        )
        experiment_id = cursor.lastrowid
        groups = []
        for group in payload.groups:
            group_cursor = connection.execute(
                """INSERT INTO experiment_groups(experiment_id, name, kind, description)
                   VALUES (?, ?, ?, ?)""",
                (experiment_id, group.name, group.kind.value, group.description),
            )
            group_id = group_cursor.lastrowid
            normalized_trays = [code.upper() for code in group.tray_codes]
            connection.executemany(
                """INSERT INTO experiment_trays(experiment_id, group_id, tray_code)
                   VALUES (?, ?, ?)""",
                [(experiment_id, group_id, code) for code in normalized_trays],
            )
            groups.append(
                ExperimentGroupRead(
                    id=group_id,
                    name=group.name,
                    kind=group.kind,
                    description=group.description,
                    tray_codes=normalized_trays,
                )
            )
    return ExperimentRead(
        id=experiment_id,
        name=payload.name,
        crop=payload.crop,
        hypothesis=payload.hypothesis,
        started_at=payload.started_at,
        ended_at=payload.ended_at,
        created_by=payload.created_by,
        groups=groups,
    )


@app.get("/api/v1/experiments", response_model=list[ExperimentListItem])
def list_experiments() -> list[ExperimentListItem]:
    with repository.connect() as connection:
        rows = connection.execute(
            """SELECT id, name, crop, started_at, ended_at
               FROM experiments ORDER BY started_at DESC, id DESC"""
        ).fetchall()
    return [ExperimentListItem(**dict(row)) for row in rows]


@app.get(
    "/api/v1/experiments/{experiment_id}/comparison",
    response_model=ExperimentComparisonRead,
)
def compare_experiment(experiment_id: int) -> ExperimentComparisonRead:
    with repository.connect() as connection:
        experiment = connection.execute(
            "SELECT id, name, started_at, ended_at FROM experiments WHERE id = ?",
            (experiment_id,),
        ).fetchone()
        if experiment is None:
            raise HTTPException(status_code=404, detail="Experiment not found")
        groups = connection.execute(
            """SELECT id, name, kind FROM experiment_groups
               WHERE experiment_id = ? ORDER BY kind, id""",
            (experiment_id,),
        ).fetchall()
        observation_rows = connection.execute(
            """SELECT et.group_id, o.seedling_id, o.captured_at, o.leaf_area_cm2
               FROM experiment_trays et
               JOIN observations o ON o.tray_code = et.tray_code
               WHERE et.experiment_id = ?
               ORDER BY et.group_id, o.seedling_id, o.captured_at""",
            (experiment_id,),
        ).fetchall()

    started_at = datetime.fromisoformat(experiment["started_at"])
    ended_at = datetime.fromisoformat(experiment["ended_at"]) if experiment["ended_at"] else None
    summaries = []
    for group in groups:
        valid_rows = [
            row
            for row in observation_rows
            if row["group_id"] == group["id"]
            and datetime.fromisoformat(row["captured_at"]) >= started_at
            and (ended_at is None or datetime.fromisoformat(row["captured_at"]) <= ended_at)
        ]
        summary = summarize_group_growth(
            group_id=group["id"],
            group_name=group["name"],
            group_kind=group["kind"],
            observation_rows=valid_rows,
        )
        summaries.append(
            GroupGrowthSummaryRead(
                group_id=summary.group_id,
                group_name=summary.group_name,
                group_kind=summary.group_kind,
                sample_size=summary.sample_size,
                mean_growth_rate_percent=summary.mean_growth_rate_percent,
                median_growth_rate_percent=summary.median_growth_rate_percent,
                standard_deviation_percent=summary.standard_deviation_percent,
                minimum_growth_rate_percent=summary.minimum_growth_rate_percent,
                maximum_growth_rate_percent=summary.maximum_growth_rate_percent,
                samples=[GrowthSampleRead(**sample.__dict__) for sample in summary.samples],
            )
        )
    return ExperimentComparisonRead(
        experiment_id=experiment_id,
        experiment_name=experiment["name"],
        groups=summaries,
        interpretation_note=(
            "Descriptive statistics only. Group differences are not evidence of causality or "
            "statistical significance without an appropriate experimental analysis."
        ),
    )


EXPERIMENT_EXPORT_FIELDS = [
    "experiment_id",
    "experiment_name",
    "group_name",
    "group_kind",
    "tray_code",
    "seedling_id",
    "captured_at",
    "leaf_area_cm2",
    "discoloration_ratio",
    "damage_ratio",
    "ai_status",
    "temperature_c",
    "pressure_hpa",
    "humidity_percent",
    "soil_moisture_percent",
    "soil_moisture_raw_adc",
    "soil_moisture_voltage_v",
    "soil_calibration_id",
    "soil_moisture_out_of_range",
    "illuminance_lux",
    "ec_ms_cm",
    "ph",
    "sensor_time_delta_seconds",
    "expert_assessment",
]


@app.get("/api/v1/experiments/{experiment_id}/export.csv")
def export_experiment_csv(experiment_id: int) -> StreamingResponse:
    query = """
    SELECT e.id AS experiment_id, e.name AS experiment_name, e.started_at, e.ended_at,
           g.name AS group_name, g.kind AS group_kind, et.tray_code,
           o.seedling_id, o.captured_at, o.leaf_area_cm2, o.discoloration_ratio,
           o.damage_ratio, o.status AS ai_status,
           sr.temperature_c, sr.pressure_hpa, sr.humidity_percent,
           sr.soil_moisture_percent, sr.soil_moisture_raw_adc,
           sr.soil_moisture_voltage_v, sr.soil_calibration_id,
           sr.soil_moisture_out_of_range, sr.illuminance_lux, sr.ec_ms_cm, sr.ph,
           csl.time_delta_seconds,
           er.assessment AS expert_assessment
    FROM experiments e
    JOIN experiment_groups g ON g.experiment_id = e.id
    JOIN experiment_trays et ON et.group_id = g.id AND et.experiment_id = e.id
    JOIN observations o ON o.tray_code = et.tray_code
    LEFT JOIN capture_observations co ON co.observation_id = o.id
    LEFT JOIN capture_sensor_links csl ON csl.capture_id = co.capture_id
    LEFT JOIN sensor_readings sr ON sr.id = csl.sensor_reading_id
    LEFT JOIN expert_reviews er ON er.id = (
        SELECT id FROM expert_reviews WHERE observation_id = o.id
        ORDER BY reviewed_at DESC LIMIT 1
    )
    WHERE e.id = ?
    ORDER BY g.kind, g.name, o.seedling_id, o.captured_at
    """
    with repository.connect() as connection:
        rows = connection.execute(query, (experiment_id,)).fetchall()
        experiment = connection.execute(
            "SELECT started_at, ended_at FROM experiments WHERE id = ?", (experiment_id,)
        ).fetchone()
    if experiment is None:
        raise HTTPException(status_code=404, detail="Experiment not found")

    started_at = datetime.fromisoformat(experiment["started_at"])
    ended_at = datetime.fromisoformat(experiment["ended_at"]) if experiment["ended_at"] else None
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=EXPERIMENT_EXPORT_FIELDS)
    writer.writeheader()
    for row in rows:
        observed_at = datetime.fromisoformat(row["captured_at"])
        if observed_at < started_at or (ended_at is not None and observed_at > ended_at):
            continue
        writer.writerow(
            {
                field: (
                    row[field]
                    if field != "sensor_time_delta_seconds"
                    else row["time_delta_seconds"]
                )
                for field in EXPERIMENT_EXPORT_FIELDS
            }
        )
    filename = f"experiment-{experiment_id}.csv"
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
