from datetime import datetime, timedelta, timezone
from pathlib import Path

import cv2
import numpy as np
from app import main
from app.repository import Repository
from fastapi.testclient import TestClient


def test_seedling_history_is_chronological_and_calculates_growth(tmp_path: Path):
    main.repository = Repository(tmp_path / "test.db")
    start = datetime(2026, 8, 1, tzinfo=timezone.utc)

    with TestClient(main.app) as client:
        assert (
            client.post(
                "/api/v1/trays",
                json={"code": "TRAY-T", "crop": "tomato", "rows": 1, "columns": 1},
            ).status_code
            == 201
        )
        for day, area in [(0, 10), (2, 12.5)]:
            response = client.post(
                "/api/v1/observations",
                json={
                    "tray_code": "TRAY-T",
                    "row": 1,
                    "column": 1,
                    "captured_at": (start + timedelta(days=day)).isoformat(),
                    "leaf_area_cm2": area,
                },
            )
            assert response.status_code == 201

        seedlings = client.get("/api/v1/seedlings").json()
        history = client.get("/api/v1/seedlings/TRAY-T-R01C01/history").json()

    assert seedlings[0]["leaf_area_cm2"] == 12.5
    assert [point["leaf_area_cm2"] for point in history] == [10, 12.5]
    assert history[0]["growth_rate_percent"] is None
    assert history[1]["growth_rate_percent"] == 25.0


def test_full_tray_image_creates_one_observation_per_cell(tmp_path: Path):
    main.repository = Repository(tmp_path / "tray.db")
    main.UPLOAD_ROOT = tmp_path / "uploads"
    image = np.full((100, 100, 3), 80, dtype=np.uint8)
    image[::10, :] = 120
    image[:, ::10] = 120
    for y, x in [(10, 10), (10, 60), (60, 10), (60, 60)]:
        image[y : y + 25, x : x + 25] = (0, 180, 0)
    success, encoded = cv2.imencode(".png", image)
    assert success

    with TestClient(main.app) as client:
        assert (
            client.post(
                "/api/v1/trays",
                json={"code": "TRAY-G", "crop": "pepper", "rows": 2, "columns": 2},
            ).status_code
            == 201
        )
        response = client.post(
            "/api/v1/trays/TRAY-G/images/analyze",
            files={"image": ("tray.png", encoded.tobytes(), "image/png")},
            data={
                "captured_at": "2026-08-17T09:00:00+09:00",
                "pixels_per_cm": "10",
                "margin_ratio": "0",
            },
        )

    assert response.status_code == 201, response.text
    body = response.json()
    assert len(body["cells"]) == 4
    assert {cell["seedling_id"] for cell in body["cells"]} == {
        "TRAY-G-R01C01",
        "TRAY-G-R01C02",
        "TRAY-G-R02C01",
        "TRAY-G-R02C02",
    }
    assert (main.UPLOAD_ROOT / body["image_path"]).exists()


def test_quality_gate_rejects_bad_capture_before_persistence(tmp_path: Path):
    main.repository = Repository(tmp_path / "quality.db")
    main.UPLOAD_ROOT = tmp_path / "uploads"
    image = np.zeros((100, 100, 3), dtype=np.uint8)
    success, encoded = cv2.imencode(".png", image)
    assert success

    with TestClient(main.app) as client:
        assert (
            client.post(
                "/api/v1/trays",
                json={"code": "TRAY-Q", "crop": "tomato", "rows": 1, "columns": 1},
            ).status_code
            == 201
        )
        response = client.post(
            "/api/v1/trays/TRAY-Q/images/analyze",
            files={"image": ("dark.png", encoded.tobytes(), "image/png")},
            data={
                "captured_at": "2026-08-18T09:00:00+09:00",
                "pixels_per_cm": "10",
            },
        )
        seedlings = client.get("/api/v1/seedlings").json()

    assert response.status_code == 422
    assert response.json()["detail"]["message"] == "Capture quality gate failed"
    assert "image_too_dark" in response.json()["detail"]["quality"]["reasons"]
    assert seedlings == []


def test_tray_endpoint_can_rectify_perspective_capture(tmp_path: Path):
    main.repository = Repository(tmp_path / "rectify.db")
    main.UPLOAD_ROOT = tmp_path / "uploads"
    image = np.full((300, 400, 3), 40, dtype=np.uint8)
    polygon = np.array([[80, 40], [340, 70], [310, 260], [50, 230]], dtype=np.int32)
    cv2.fillConvexPoly(image, polygon, (110, 110, 110))
    cv2.polylines(image, [polygon], True, (240, 240, 240), 5)
    success, encoded = cv2.imencode(".png", image)
    assert success

    with TestClient(main.app) as client:
        assert (
            client.post(
                "/api/v1/trays",
                json={"code": "TRAY-R", "crop": "lettuce", "rows": 2, "columns": 2},
            ).status_code
            == 201
        )
        response = client.post(
            "/api/v1/trays/TRAY-R/images/analyze",
            files={"image": ("perspective.png", encoded.tobytes(), "image/png")},
            data={
                "captured_at": "2026-08-19T09:00:00+09:00",
                "pixels_per_cm": "10",
                "rectify": "true",
            },
        )

    assert response.status_code == 201, response.text
    rectification = response.json()["rectification"]
    assert rectification["applied"] is True
    assert len(rectification["corners"]) == 4
    assert rectification["source_area_ratio"] > 0.35


def test_sensor_readings_are_validated_and_returned_latest_first(tmp_path: Path):
    main.repository = Repository(tmp_path / "sensors.db")
    with TestClient(main.app) as client:
        assert (
            client.post(
                "/api/v1/trays",
                json={"code": "TRAY-S", "crop": "tomato", "rows": 1, "columns": 1},
            ).status_code
            == 201
        )
        empty = client.post(
            "/api/v1/trays/TRAY-S/sensor-readings",
            json={"measured_at": "2026-08-20T09:00:00+09:00", "source": "edge-01"},
        )
        naive_time = client.post(
            "/api/v1/trays/TRAY-S/sensor-readings",
            json={"measured_at": "2026-08-20T09:00:00", "temperature_c": 24},
        )
        for hour, temperature in [(9, 24.2), (10, 25.1)]:
            response = client.post(
                "/api/v1/trays/TRAY-S/sensor-readings",
                json={
                    "measured_at": f"2026-08-20T{hour:02d}:00:00+09:00",
                    "source": "edge-01",
                    "temperature_c": temperature,
                    "humidity_percent": 61,
                    "soil_moisture_percent": 43,
                    "illuminance_lux": 12000,
                    "ec_ms_cm": 1.7,
                    "ph": 6.2,
                },
            )
            assert response.status_code == 201, response.text
        readings = client.get("/api/v1/trays/TRAY-S/sensor-readings").json()

    assert empty.status_code == 422
    assert naive_time.status_code == 422
    assert [reading["temperature_c"] for reading in readings] == [25.1, 24.2]


def test_tray_capture_links_nearest_sensor_context(tmp_path: Path):
    main.repository = Repository(tmp_path / "multimodal.db")
    main.UPLOAD_ROOT = tmp_path / "uploads"
    image = np.full((100, 100, 3), 80, dtype=np.uint8)
    image[::10, :] = 120
    image[:, ::10] = 120
    image[20:80, 30:70] = (0, 180, 0)
    success, encoded = cv2.imencode(".png", image)
    assert success

    with TestClient(main.app) as client:
        assert (
            client.post(
                "/api/v1/trays",
                json={"code": "TRAY-M", "crop": "tomato", "rows": 1, "columns": 1},
            ).status_code
            == 201
        )
        sensor = client.post(
            "/api/v1/trays/TRAY-M/sensor-readings",
            json={
                "measured_at": "2026-08-20T09:08:00+09:00",
                "source": "edge-01",
                "temperature_c": 24.5,
                "humidity_percent": 62,
            },
        ).json()
        response = client.post(
            "/api/v1/trays/TRAY-M/images/analyze",
            files={"image": ("tray.png", encoded.tobytes(), "image/png")},
            data={
                "captured_at": "2026-08-20T09:10:00+09:00",
                "pixels_per_cm": "10",
            },
        )

    assert response.status_code == 201, response.text
    context = response.json()["sensor_context"]
    assert context["reading_id"] == sensor["id"]
    assert context["time_delta_seconds"] == 120
    assert context["temperature_c"] == 24.5
    with main.repository.connect() as connection:
        link = connection.execute("SELECT * FROM capture_sensor_links").fetchone()
    assert link["sensor_reading_id"] == sensor["id"]
