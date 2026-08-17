from datetime import datetime, timezone

from app.telemetry import nearest_sensor_reading


def test_nearest_sensor_reading_compares_timezone_aware_instants():
    capture = datetime(2026, 8, 20, 0, 10, tzinfo=timezone.utc)
    readings = [
        {"id": 1, "measured_at": "2026-08-20T09:00:00+09:00"},
        {"id": 2, "measured_at": "2026-08-20T09:08:00+09:00"},
    ]

    match = nearest_sensor_reading(capture, readings, maximum_age_minutes=30)

    assert match.reading_id == 2
    assert match.time_delta_seconds == 120


def test_nearest_sensor_reading_respects_maximum_age():
    capture = datetime(2026, 8, 20, 0, 0, tzinfo=timezone.utc)
    readings = [{"id": 1, "measured_at": "2026-08-20T00:31:00+00:00"}]
    assert nearest_sensor_reading(capture, readings, maximum_age_minutes=30) is None


def test_nearest_sensor_reading_rejects_naive_capture_time():
    capture = datetime(2026, 8, 20, 0, 0)
    try:
        nearest_sensor_reading(capture, [], maximum_age_minutes=30)
    except ValueError as error:
        assert "timezone" in str(error)
    else:
        raise AssertionError("Expected timezone validation error")
