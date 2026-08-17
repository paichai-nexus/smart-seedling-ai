from __future__ import annotations

import mimetypes
from datetime import datetime, timezone
from pathlib import Path

import httpx

from edge.agent.queue import CaptureQueue, QueuedCapture


class CaptureUploader:
    def __init__(
        self,
        queue: CaptureQueue,
        server_url: str,
        client: httpx.Client | None = None,
    ) -> None:
        self.queue = queue
        self.server_url = server_url.rstrip("/")
        self.client = client or httpx.Client(timeout=60)

    def upload_due(self, now: datetime, limit: int = 20) -> int:
        sent = 0
        for capture in self.queue.due(now, limit):
            try:
                self._upload(capture)
            except (OSError, httpx.HTTPError) as exc:
                self.queue.mark_failed(capture.id, str(exc), now)
                continue
            self.queue.mark_sent(capture.id, datetime.now(timezone.utc))
            sent += 1
        return sent

    def _upload(self, capture: QueuedCapture) -> None:
        path = Path(capture.image_path)
        if not path.is_file():
            raise OSError(f"queued image is missing: {path}")
        tray_code = str(capture.metadata["tray_code"])
        captured_at = str(capture.metadata["captured_at"])
        mime_type = mimetypes.guess_type(path.name)[0] or "image/jpeg"
        with path.open("rb") as image_file:
            response = self.client.post(
                f"{self.server_url}/api/v1/trays/{tray_code}/images/analyze",
                data={"captured_at": captured_at},
                files={"image": (path.name, image_file, mime_type)},
            )
        response.raise_for_status()
