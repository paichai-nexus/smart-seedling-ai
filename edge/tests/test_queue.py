from datetime import datetime, timedelta, timezone
from pathlib import Path

from edge.agent.queue import CaptureQueue


def test_capture_queue_retries_with_exponential_backoff(tmp_path: Path):
    image = tmp_path / "capture.png"
    image.write_bytes(b"image-bytes")
    queue = CaptureQueue(tmp_path / "queue.db")
    queue.initialize()
    now = datetime(2026, 8, 25, 0, 0, tzinfo=timezone.utc)
    capture_id = queue.enqueue(image, {"tray_code": "TRAY-A"}, now)

    first = queue.due(now)[0]
    retry_at = queue.mark_failed(first.id, "network unavailable", now)

    assert first.id == capture_id
    assert retry_at == now + timedelta(seconds=30)
    assert queue.due(now) == []
    assert queue.due(retry_at)[0].attempts == 1


def test_sent_capture_is_retained_for_audit_but_not_retried(tmp_path: Path):
    image = tmp_path / "capture.jpg"
    image.write_bytes(b"image-bytes")
    queue = CaptureQueue(tmp_path / "queue.db")
    queue.initialize()
    now = datetime(2026, 8, 25, 0, 0, tzinfo=timezone.utc)
    capture_id = queue.enqueue(image, {"tray_code": "TRAY-A"}, now)

    queue.mark_sent(capture_id, now)

    assert queue.pending_count() == 0
    assert queue.due(now + timedelta(days=1)) == []


def test_duplicate_capture_metadata_is_idempotent(tmp_path: Path):
    image = tmp_path / "capture.jpg"
    image.write_bytes(b"same-image")
    queue = CaptureQueue(tmp_path / "queue.db")
    queue.initialize()
    now = datetime(2026, 8, 25, 0, 0, tzinfo=timezone.utc)

    first = queue.enqueue(image, {"tray_code": "TRAY-A"}, now)
    second = queue.enqueue(image, {"tray_code": "TRAY-A"}, now)

    assert first == second
    assert queue.pending_count() == 1


def test_capture_time_is_normalized_to_utc_for_due_comparison(tmp_path: Path):
    image = tmp_path / "capture.jpg"
    image.write_bytes(b"image-bytes")
    queue = CaptureQueue(tmp_path / "queue.db")
    queue.initialize()
    korea_time = datetime(2026, 8, 25, 9, 0, tzinfo=timezone(timedelta(hours=9)))

    queue.enqueue(image, {"tray_code": "TRAY-A"}, korea_time)

    assert len(queue.due(datetime(2026, 8, 25, 0, 0, tzinfo=timezone.utc))) == 1
