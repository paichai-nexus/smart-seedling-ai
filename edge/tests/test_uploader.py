from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx

from edge.agent.queue import CaptureQueue
from edge.agent.uploader import CaptureUploader


def make_queue(tmp_path: Path) -> tuple[CaptureQueue, datetime]:
    image = tmp_path / "capture.jpg"
    image.write_bytes(b"jpeg-data")
    queue = CaptureQueue(tmp_path / "queue.db")
    queue.initialize()
    now = datetime(2026, 8, 25, 9, 0, tzinfo=timezone(timedelta(hours=9)))
    queue.enqueue(
        image,
        {"tray_code": "TRAY-A", "captured_at": now.isoformat()},
        now,
    )
    return queue, now


def test_uploader_posts_capture_and_marks_it_sent(tmp_path: Path):
    queue, now = make_queue(tmp_path)

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/v1/trays/TRAY-A/images/analyze"
        assert b'filename="capture.jpg"' in request.content
        assert b"2026-08-25T09:00:00+09:00" in request.content
        return httpx.Response(201, json={"ok": True})

    client = httpx.Client(transport=httpx.MockTransport(handler))
    uploader = CaptureUploader(queue, "http://server.example/", client)

    assert uploader.upload_due(now) == 1
    assert queue.pending_count() == 0


def test_uploader_keeps_capture_for_retry_after_network_failure(tmp_path: Path):
    queue, now = make_queue(tmp_path)

    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("offline", request=request)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    uploader = CaptureUploader(queue, "http://server.example", client)

    assert uploader.upload_due(now) == 0
    assert queue.pending_count() == 1
    assert queue.due(now) == []
    assert queue.due(now + timedelta(seconds=30))[0].attempts == 1
