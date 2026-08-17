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
