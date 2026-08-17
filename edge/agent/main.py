from __future__ import annotations

import argparse
import logging
import time
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from edge.agent.camera import capture_image
from edge.agent.queue import CaptureQueue
from edge.agent.uploader import CaptureUploader

LOGGER = logging.getLogger("smart-seedling-edge")


def run_cycle(
    queue: CaptureQueue,
    uploader: CaptureUploader,
    tray_code: str,
    timezone_name: str,
    image_directory: Path,
) -> None:
    captured_at = datetime.now(ZoneInfo(timezone_name))
    sent = uploader.upload_due(captured_at)
    image_path = capture_image(image_directory, captured_at)
    queue.enqueue(
        image_path,
        {"tray_code": tray_code.upper(), "captured_at": captured_at.isoformat()},
        captured_at,
    )
    sent += uploader.upload_due(captured_at)
    LOGGER.info("capture queued; sent=%d pending=%d", sent, queue.pending_count())


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Smart Seedling Raspberry Pi edge agent")
    parser.add_argument("--server-url", required=True)
    parser.add_argument("--tray-code", required=True)
    parser.add_argument("--timezone", default="Asia/Seoul")
    parser.add_argument("--interval-seconds", type=int, default=3600)
    parser.add_argument("--data-directory", type=Path, default=Path("edge/data"))
    parser.add_argument("--once", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.interval_seconds < 60:
        raise SystemExit("--interval-seconds must be at least 60")
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    args.data_directory.mkdir(parents=True, exist_ok=True)
    queue = CaptureQueue(args.data_directory / "capture-queue.db")
    queue.initialize()
    uploader = CaptureUploader(queue, args.server_url)
    while True:
        try:
            run_cycle(
                queue,
                uploader,
                args.tray_code,
                args.timezone,
                args.data_directory / "captures",
            )
        except Exception:
            LOGGER.exception("capture cycle failed")
            if args.once:
                raise
        if args.once:
            break
        time.sleep(args.interval_seconds)


if __name__ == "__main__":
    main()
