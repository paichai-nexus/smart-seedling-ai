from __future__ import annotations

import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse

from .domain import ObservationMetrics, classify_status, growth_rate_percent, stable_seedling_id
from .repository import Repository
from .schemas import DashboardSummary, ObservationCreate, ObservationRead, TrayCreate

ROOT = Path(__file__).resolve().parents[2]
repository = Repository(os.getenv("SMART_SEEDLING_DB", str(ROOT / "smart_seedling.db")))


@asynccontextmanager
async def lifespan(_: FastAPI):
    repository.initialize()
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
