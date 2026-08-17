from datetime import datetime, timedelta, timezone
from pathlib import Path

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
