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


def test_expert_review_removes_observation_from_queue(tmp_path: Path):
    main.repository = Repository(tmp_path / "reviews.db")
    with TestClient(main.app) as client:
        client.post(
            "/api/v1/trays",
            json={"code": "TRAY-E", "crop": "tomato", "rows": 1, "columns": 1},
        )
        observation = client.post(
            "/api/v1/observations",
            json={
                "tray_code": "TRAY-E",
                "row": 1,
                "column": 1,
                "captured_at": "2026-08-21T09:00:00+09:00",
                "leaf_area_cm2": 10,
                "discoloration_ratio": 0.25,
            },
        ).json()
        assert len(client.get("/api/v1/reviews/queue").json()) == 1
        review = client.post(
            f"/api/v1/observations/{observation['id']}/reviews",
            json={
                "reviewer": "Professor Kim",
                "assessment": "uncertain",
                "observable_notes": "Yellowing visible on lower leaves",
                "possible_cause_notes": "Check EC, moisture, and recent fertilization",
                "reviewed_at": "2026-08-21T10:00:00+09:00",
            },
        )
        queue = client.get("/api/v1/reviews/queue").json()

    assert review.status_code == 201, review.text
    assert queue == []


def test_knowledge_rule_is_hidden_until_expert_approval(tmp_path: Path):
    main.repository = Repository(tmp_path / "knowledge.db")
    with TestClient(main.app) as client:
        draft = client.post(
            "/api/v1/knowledge-rules",
            json={
                "title": "Yellowing with reduced growth",
                "observable_signals": ["yellowing", "growth_slowdown"],
                "possible_causes": ["nitrogen deficiency", "overwatering", "low light"],
                "required_checks": ["EC", "soil moisture", "recent fertilization"],
                "suggested_actions": ["continue observation", "request expert review"],
                "safety_note": (
                    "Do not change fertilizer or pesticide dose without expert approval."
                ),
                "created_by": "student-team",
            },
        ).json()
        assert client.get("/api/v1/knowledge-rules").json() == []
        approval = client.post(
            f"/api/v1/knowledge-rules/{draft['id']}/approve",
            json={
                "approved_by": "Professor Kim",
                "approved_at": "2026-08-21T11:00:00+09:00",
            },
        )
        rules = client.get("/api/v1/knowledge-rules").json()

    assert approval.status_code == 200, approval.text
    assert rules[0]["status"] == "approved"
    assert rules[0]["approved_by"] == "Professor Kim"


def test_recommendations_use_only_approved_matching_rules(tmp_path: Path):
    main.repository = Repository(tmp_path / "recommendations.db")
    with TestClient(main.app) as client:
        client.post(
            "/api/v1/trays",
            json={"code": "TRAY-K", "crop": "tomato", "rows": 1, "columns": 1},
        )
        observation = client.post(
            "/api/v1/observations",
            json={
                "tray_code": "TRAY-K",
                "row": 1,
                "column": 1,
                "captured_at": "2026-08-22T09:00:00+09:00",
                "leaf_area_cm2": 10,
                "discoloration_ratio": 0.12,
            },
        ).json()
        rule_payload = {
            "title": "Discoloration triage",
            "observable_signals": ["discoloration"],
            "possible_causes": ["nutrition", "moisture", "light"],
            "required_checks": ["EC", "soil moisture", "illuminance"],
            "suggested_actions": ["request expert review"],
            "safety_note": "Do not alter inputs before measurement and expert review.",
            "created_by": "student-team",
        }
        approved = client.post("/api/v1/knowledge-rules", json=rule_payload).json()
        client.post(
            f"/api/v1/knowledge-rules/{approved['id']}/approve",
            json={
                "approved_by": "Professor Kim",
                "approved_at": "2026-08-22T10:00:00+09:00",
            },
        )
        client.post(
            "/api/v1/knowledge-rules",
            json={**rule_payload, "title": "Unapproved rule"},
        )
        response = client.get(f"/api/v1/observations/{observation['id']}/recommendations")

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["observed_signals"] == ["discoloration"]
    assert len(body["rules"]) == 1
    assert body["rules"][0]["rule_id"] == approved["id"]
    assert body["rules"][0]["matched_signals"] == ["discoloration"]
    assert "not a diagnosis" in body["disclaimer"]


def test_controlled_experiment_exports_grouped_observations(tmp_path: Path):
    main.repository = Repository(tmp_path / "experiment.db")
    with TestClient(main.app) as client:
        for code in ("TRAY-C", "TRAY-T"):
            client.post(
                "/api/v1/trays",
                json={"code": code, "crop": "tomato", "rows": 1, "columns": 1},
            )
            client.post(
                "/api/v1/observations",
                json={
                    "tray_code": code,
                    "row": 1,
                    "column": 1,
                    "captured_at": "2026-08-23T09:00:00+09:00",
                    "leaf_area_cm2": 12 if code == "TRAY-C" else 14,
                },
            )
        experiment = client.post(
            "/api/v1/experiments",
            json={
                "name": "Irrigation pilot",
                "crop": "tomato",
                "hypothesis": "Adjusted irrigation changes projected leaf area.",
                "started_at": "2026-08-22T00:00:00+09:00",
                "ended_at": "2026-08-30T00:00:00+09:00",
                "created_by": "student-team",
                "groups": [
                    {
                        "name": "standard irrigation",
                        "kind": "control",
                        "description": "Existing protocol",
                        "tray_codes": ["TRAY-C"],
                    },
                    {
                        "name": "adjusted irrigation",
                        "kind": "treatment",
                        "description": "Expert-defined treatment",
                        "tray_codes": ["TRAY-T"],
                    },
                ],
            },
        )
        export = client.get(f"/api/v1/experiments/{experiment.json()['id']}/export.csv")

    assert experiment.status_code == 201, experiment.text
    assert export.status_code == 200
    lines = export.text.strip().splitlines()
    assert len(lines) == 3
    assert "group_kind" in lines[0]
    assert any("control" in line and "TRAY-C" in line for line in lines[1:])
    assert any("treatment" in line and "TRAY-T" in line for line in lines[1:])


def test_experiment_comparison_reports_group_growth_statistics(tmp_path: Path):
    main.repository = Repository(tmp_path / "comparison.db")
    with TestClient(main.app) as client:
        for code, areas in (("CONTROL", (10, 12)), ("TREATMENT", (10, 15))):
            client.post(
                "/api/v1/trays",
                json={"code": code, "crop": "tomato", "rows": 1, "columns": 1},
            )
            for day, area in enumerate(areas, start=1):
                client.post(
                    "/api/v1/observations",
                    json={
                        "tray_code": code,
                        "row": 1,
                        "column": 1,
                        "captured_at": f"2026-08-{day:02d}T09:00:00+09:00",
                        "leaf_area_cm2": area,
                    },
                )
        experiment = client.post(
            "/api/v1/experiments",
            json={
                "name": "Growth comparison",
                "crop": "tomato",
                "hypothesis": "Treatment changes projected leaf-area growth.",
                "started_at": "2026-08-01T00:00:00+09:00",
                "ended_at": "2026-08-03T00:00:00+09:00",
                "created_by": "student-team",
                "groups": [
                    {
                        "name": "Control",
                        "kind": "control",
                        "description": "Standard protocol",
                        "tray_codes": ["CONTROL"],
                    },
                    {
                        "name": "Treatment",
                        "kind": "treatment",
                        "description": "Candidate protocol",
                        "tray_codes": ["TREATMENT"],
                    },
                ],
            },
        ).json()
        comparison = client.get(f"/api/v1/experiments/{experiment['id']}/comparison").json()

    groups = {group["group_kind"]: group for group in comparison["groups"]}
    assert groups["control"]["mean_growth_rate_percent"] == 20
    assert groups["treatment"]["mean_growth_rate_percent"] == 50
    assert groups["control"]["sample_size"] == 1
    assert "not evidence of causality" in comparison["interpretation_note"]


def test_capture_profile_is_created_and_updated_per_tray(tmp_path: Path):
    main.repository = Repository(tmp_path / "profile.db")
    with TestClient(main.app) as client:
        client.post(
            "/api/v1/trays",
            json={"code": "TRAY-P", "crop": "pepper", "rows": 2, "columns": 2},
        )
        first = client.put(
            "/api/v1/trays/TRAY-P/capture-profile",
            json={
                "pixels_per_cm": 42.5,
                "margin_ratio": 0.1,
                "rectify": True,
                "minimum_tray_area_ratio": 0.3,
                "maximum_sensor_age_minutes": 20,
                "updated_by": "student-team",
                "updated_at": "2026-08-24T09:00:00+09:00",
            },
        )
        second = client.put(
            "/api/v1/trays/TRAY-P/capture-profile",
            json={
                **first.json(),
                "pixels_per_cm": 43,
                "updated_at": "2026-08-24T10:00:00+09:00",
            },
        )
        profile = client.get("/api/v1/trays/TRAY-P/capture-profile")

    assert first.status_code == 200, first.text
    assert second.status_code == 200, second.text
    assert profile.json()["pixels_per_cm"] == 43
    assert profile.json()["rectify"] is True


def test_tray_analysis_uses_stored_capture_profile(tmp_path: Path):
    main.repository = Repository(tmp_path / "profile-analysis.db")
    main.UPLOAD_ROOT = tmp_path / "uploads"
    image = np.full((100, 100, 3), 80, dtype=np.uint8)
    image[::10, :] = 120
    image[:, ::10] = 120
    image[20:80, 30:70] = (0, 180, 0)
    success, encoded = cv2.imencode(".png", image)
    assert success

    with TestClient(main.app) as client:
        client.post(
            "/api/v1/trays",
            json={"code": "TRAY-CP", "crop": "pepper", "rows": 1, "columns": 1},
        )
        client.put(
            "/api/v1/trays/TRAY-CP/capture-profile",
            json={
                "pixels_per_cm": 10,
                "margin_ratio": 0,
                "rectify": False,
                "minimum_tray_area_ratio": 0.25,
                "maximum_sensor_age_minutes": 15,
                "updated_by": "student-team",
                "updated_at": "2026-08-24T10:00:00+09:00",
            },
        )
        response = client.post(
            "/api/v1/trays/TRAY-CP/images/analyze",
            files={"image": ("tray.png", encoded.tobytes(), "image/png")},
            data={"captured_at": "2026-08-24T11:00:00+09:00"},
        )

    assert response.status_code == 201, response.text
    settings = response.json()["capture_settings"]
    assert settings["source"] == "profile"
    assert settings["pixels_per_cm"] == 10
    assert settings["maximum_sensor_age_minutes"] == 15
