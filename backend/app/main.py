from __future__ import annotations

import json
import os
from contextlib import asynccontextmanager
from datetime import datetime
from hashlib import sha256
from pathlib import Path
from uuid import uuid4

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from typing_extensions import Annotated

from .domain import ObservationMetrics, classify_status, growth_rate_percent, stable_seedling_id
from .recommendations import derive_observable_signals, rank_knowledge_rules
from .repository import Repository
from .schemas import (
    CaptureQualityRead,
    DashboardSummary,
    ExpertReviewCreate,
    ExpertReviewRead,
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
    TrayAnalysisRead,
    TrayCellAnalysis,
    TrayCreate,
    TrayRectificationRead,
)
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
    pixels_per_cm: Annotated[float, Form(gt=0)],
    margin_ratio: Annotated[float, Form(ge=0, lt=0.4)] = 0.08,
    rectify: Annotated[bool, Form()] = False,
    minimum_tray_area_ratio: Annotated[float, Form(gt=0, lt=1)] = 0.25,
    maximum_sensor_age_minutes: Annotated[float, Form(ge=0, le=1440)] = 30,
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
        sensor_rows = connection.execute(
            """SELECT id, measured_at, source, temperature_c, humidity_percent,
                      soil_moisture_percent, illuminance_lux, ec_ms_cm, ph
               FROM sensor_readings WHERE tray_code = ?
               ORDER BY measured_at DESC LIMIT 5000""",
            (tray_code,),
        ).fetchall()
    if tray is None:
        raise HTTPException(status_code=404, detail="Tray not found")
    sensor_match = nearest_sensor_reading(
        captured_at,
        sensor_rows,
        maximum_age_minutes=maximum_sensor_age_minutes,
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
        if rectify:
            rectification = detect_and_rectify_tray(decoded, minimum_tray_area_ratio)
            analysis_image = rectification.image
        else:
            rectification = None
            analysis_image = decoded
        cells = split_tray_grid(analysis_image, tray["rows"], tray["columns"], margin_ratio)
    except HTTPException:
        raise
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    results = []
    for cell in cells:
        analysis = analyze_green_leaf_area(cell.image, pixels_per_cm)
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
                    pixels_per_cm,
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
                time_delta_seconds=sensor_match.time_delta_seconds,
                temperature_c=matched_sensor["temperature_c"],
                humidity_percent=matched_sensor["humidity_percent"],
                soil_moisture_percent=matched_sensor["soil_moisture_percent"],
                illuminance_lux=matched_sensor["illuminance_lux"],
                ec_ms_cm=matched_sensor["ec_ms_cm"],
                ph=matched_sensor["ph"],
            )
            if matched_sensor and sensor_match
            else None
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
        try:
            cursor = connection.execute(
                """INSERT INTO sensor_readings(
                       tray_code, measured_at, source, temperature_c, humidity_percent,
                       soil_moisture_percent, illuminance_lux, ec_ms_cm, ph
                   ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    tray_code,
                    payload.measured_at.isoformat(),
                    payload.source,
                    payload.temperature_c,
                    payload.humidity_percent,
                    payload.soil_moisture_percent,
                    payload.illuminance_lux,
                    payload.ec_ms_cm,
                    payload.ph,
                ),
            )
        except Exception as exc:
            raise HTTPException(status_code=409, detail="Sensor reading already exists") from exc
    return SensorReadingRead(id=cursor.lastrowid, tray_code=tray_code, **payload.model_dump())


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
            """SELECT id, tray_code, measured_at, source, temperature_c,
                      humidity_percent, soil_moisture_percent, illuminance_lux, ec_ms_cm, ph
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
