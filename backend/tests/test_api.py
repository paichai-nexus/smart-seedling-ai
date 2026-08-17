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
    image = np.zeros((100, 100, 3), dtype=np.uint8)
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
