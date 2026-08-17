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
