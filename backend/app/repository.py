from __future__ import annotations

import sqlite3
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS trays (
    code TEXT PRIMARY KEY,
    crop TEXT NOT NULL,
    rows INTEGER NOT NULL CHECK(rows > 0),
    columns INTEGER NOT NULL CHECK(columns > 0),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS observations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    seedling_id TEXT NOT NULL,
    tray_code TEXT NOT NULL REFERENCES trays(code),
    cell_row INTEGER NOT NULL,
    cell_column INTEGER NOT NULL,
    captured_at TEXT NOT NULL,
    leaf_area_cm2 REAL NOT NULL,
    discoloration_ratio REAL NOT NULL,
    damage_ratio REAL NOT NULL,
    confidence REAL NOT NULL,
    status TEXT NOT NULL,
    temperature_c REAL,
    humidity_percent REAL,
    soil_moisture_percent REAL,
    UNIQUE(seedling_id, captured_at)
);
CREATE INDEX IF NOT EXISTS observations_seedling_time
ON observations(seedling_id, captured_at DESC);
CREATE TABLE IF NOT EXISTS image_assets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    observation_id INTEGER NOT NULL REFERENCES observations(id),
    relative_path TEXT NOT NULL UNIQUE,
    sha256 TEXT NOT NULL,
    mime_type TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS tray_captures (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tray_code TEXT NOT NULL REFERENCES trays(code),
    captured_at TEXT NOT NULL,
    relative_path TEXT NOT NULL UNIQUE,
    sha256 TEXT NOT NULL,
    mime_type TEXT NOT NULL,
    pixels_per_cm REAL NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(tray_code, captured_at)
);
CREATE TABLE IF NOT EXISTS capture_observations (
    capture_id INTEGER NOT NULL REFERENCES tray_captures(id),
    observation_id INTEGER NOT NULL REFERENCES observations(id),
    PRIMARY KEY(capture_id, observation_id)
);
CREATE TABLE IF NOT EXISTS sensor_readings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tray_code TEXT NOT NULL REFERENCES trays(code),
    measured_at TEXT NOT NULL,
    source TEXT NOT NULL,
    temperature_c REAL,
    humidity_percent REAL CHECK(humidity_percent BETWEEN 0 AND 100),
    soil_moisture_percent REAL CHECK(soil_moisture_percent BETWEEN 0 AND 100),
    illuminance_lux REAL CHECK(illuminance_lux >= 0),
    ec_ms_cm REAL CHECK(ec_ms_cm >= 0),
    ph REAL CHECK(ph BETWEEN 0 AND 14),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(tray_code, measured_at, source),
    CHECK(
        temperature_c IS NOT NULL OR humidity_percent IS NOT NULL OR
        soil_moisture_percent IS NOT NULL OR illuminance_lux IS NOT NULL OR
        ec_ms_cm IS NOT NULL OR ph IS NOT NULL
    )
);
CREATE INDEX IF NOT EXISTS sensor_readings_tray_time
ON sensor_readings(tray_code, measured_at DESC);
CREATE TABLE IF NOT EXISTS capture_sensor_links (
    capture_id INTEGER PRIMARY KEY REFERENCES tray_captures(id),
    sensor_reading_id INTEGER NOT NULL REFERENCES sensor_readings(id),
    time_delta_seconds REAL NOT NULL CHECK(time_delta_seconds >= 0),
    linked_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS expert_reviews (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    observation_id INTEGER NOT NULL REFERENCES observations(id),
    reviewer TEXT NOT NULL,
    assessment TEXT NOT NULL CHECK(assessment IN ('healthy', 'warning', 'abnormal', 'uncertain')),
    observable_notes TEXT NOT NULL,
    possible_cause_notes TEXT,
    reviewed_at TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(observation_id, reviewer, reviewed_at)
);
CREATE INDEX IF NOT EXISTS expert_reviews_observation
ON expert_reviews(observation_id, reviewed_at DESC);
CREATE TABLE IF NOT EXISTS knowledge_rules (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    observable_signals_json TEXT NOT NULL,
    possible_causes_json TEXT NOT NULL,
    required_checks_json TEXT NOT NULL,
    suggested_actions_json TEXT NOT NULL,
    safety_note TEXT NOT NULL,
    status TEXT NOT NULL CHECK(status IN ('draft', 'approved', 'retired')) DEFAULT 'draft',
    created_by TEXT NOT NULL,
    approved_by TEXT,
    approved_at TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CHECK(status != 'approved' OR (approved_by IS NOT NULL AND approved_at IS NOT NULL))
);
CREATE TABLE IF NOT EXISTS experiments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    crop TEXT NOT NULL,
    hypothesis TEXT NOT NULL,
    started_at TEXT NOT NULL,
    ended_at TEXT,
    created_by TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS experiment_groups (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    experiment_id INTEGER NOT NULL REFERENCES experiments(id),
    name TEXT NOT NULL,
    kind TEXT NOT NULL CHECK(kind IN ('control', 'treatment')),
    description TEXT NOT NULL,
    UNIQUE(experiment_id, name)
);
CREATE TABLE IF NOT EXISTS experiment_trays (
    experiment_id INTEGER NOT NULL REFERENCES experiments(id),
    group_id INTEGER NOT NULL REFERENCES experiment_groups(id),
    tray_code TEXT NOT NULL REFERENCES trays(code),
    assigned_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY(experiment_id, tray_code)
);
CREATE TABLE IF NOT EXISTS capture_profiles (
    tray_code TEXT PRIMARY KEY REFERENCES trays(code),
    pixels_per_cm REAL NOT NULL CHECK(pixels_per_cm > 0),
    margin_ratio REAL NOT NULL CHECK(margin_ratio >= 0 AND margin_ratio < 0.4),
    rectify INTEGER NOT NULL CHECK(rectify IN (0, 1)),
    minimum_tray_area_ratio REAL NOT NULL
        CHECK(minimum_tray_area_ratio > 0 AND minimum_tray_area_ratio < 1),
    maximum_sensor_age_minutes REAL NOT NULL
        CHECK(maximum_sensor_age_minutes >= 0 AND maximum_sensor_age_minutes <= 1440),
    updated_by TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
"""


class Repository:
    def __init__(self, path: str | Path) -> None:
        self.path = str(path)

    def connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    def initialize(self) -> None:
        with self.connect() as connection:
            connection.executescript(SCHEMA)
