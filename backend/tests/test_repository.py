import sqlite3
from pathlib import Path

from app.repository import Repository


def test_repository_migrates_existing_sensor_table(tmp_path: Path):
    path = tmp_path / "legacy.db"
    with sqlite3.connect(path) as connection:
        connection.execute(
            """CREATE TABLE sensor_readings (
                   id INTEGER PRIMARY KEY,
                   tray_code TEXT,
                   measured_at TEXT,
                   source TEXT,
                   temperature_c REAL
               )"""
        )

    repository = Repository(path)
    repository.initialize()

    with repository.connect() as connection:
        columns = {row["name"] for row in connection.execute("PRAGMA table_info(sensor_readings)")}
    assert {"pressure_hpa", "soil_moisture_raw_adc", "soil_moisture_voltage_v"} <= columns
