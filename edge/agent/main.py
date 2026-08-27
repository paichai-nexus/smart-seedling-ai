from __future__ import annotations

import argparse
import logging
import time
from datetime import datetime
from pathlib import Path
from typing import Optional
from zoneinfo import ZoneInfo

from edge.agent.camera import capture_image
from edge.agent.queue import CaptureQueue
from edge.agent.uploader import CaptureUploader
from edge.sensors.manager import SensorManager


LOGGER = logging.getLogger(
    "smart-seedling-edge"
)


def parse_i2c_address(
    value: str,
) -> int:

    address = int(
        value,
        0,
    )

    if not 0x03 <= address <= 0x77:
        raise argparse.ArgumentTypeError(
            "I2C address must be between 0x03 and 0x77"
        )

    return address


def run_cycle(
    queue: CaptureQueue,
    uploader: CaptureUploader,
    tray_code: str,
    timezone_name: str,
    image_directory: Path,
    sensor_manager: Optional[SensorManager] = None,
) -> None:

    captured_at = datetime.now(
        ZoneInfo(timezone_name)
    )

    if sensor_manager is not None:
        try:
            reading = sensor_manager.read_and_upload(
                captured_at
            )

            LOGGER.info(
                "sensor reading uploaded; id=%s",
                reading.get("id"),
            )

        except Exception:
            LOGGER.exception(
                "sensor acquisition/upload failed; "
                "continuing with image capture"
            )

    sent = uploader.upload_due(
        captured_at
    )

    image_path = capture_image(
        image_directory,
        captured_at,
    )

    queue.enqueue(
        image_path,
        {
            "tray_code": tray_code.upper(),
            "captured_at": captured_at.isoformat(),
        },
        captured_at,
    )

    sent += uploader.upload_due(
        captured_at
    )

    LOGGER.info(
        "capture queued; sent=%d pending=%d",
        sent,
        queue.pending_count(),
    )


def parse_args() -> argparse.Namespace:

    parser = argparse.ArgumentParser(
        description="Smart Seedling Raspberry Pi edge agent"
    )

    parser.add_argument(
        "--server-url",
        required=True,
    )

    parser.add_argument(
        "--tray-code",
        required=True,
    )

    parser.add_argument(
        "--timezone",
        default="Asia/Seoul",
    )

    parser.add_argument(
        "--interval-seconds",
        type=int,
        default=3600,
    )

    parser.add_argument(
        "--data-directory",
        type=Path,
        default=Path("edge/data"),
    )

    parser.add_argument(
        "--enable-sensors",
        action="store_true",
    )

    parser.add_argument(
        "--sensor-source",
        default="raspberry-pi-edge",
    )

    parser.add_argument(
        "--sensor-id",
        default="seedling-node-01",
    )

    parser.add_argument(
        "--bme280-address",
        type=parse_i2c_address,
        default=0x77,
    )

    parser.add_argument(
        "--veml7700-address",
        type=parse_i2c_address,
        default=0x10,
    )

    parser.add_argument(
        "--ads1115-address",
        type=parse_i2c_address,
        default=0x48,
    )

    parser.add_argument(
        "--soil-channel",
        type=int,
        choices=range(4),
        default=0,
    )

    parser.add_argument(
        "--once",
        action="store_true",
    )

    return parser.parse_args()


def build_sensor_manager(
    args: argparse.Namespace,
) -> Optional[SensorManager]:

    if not args.enable_sensors:
        return None

    try:
        return SensorManager.from_hardware(
            server_url=args.server_url,
            tray_code=args.tray_code,
            source=args.sensor_source,
            sensor_id=args.sensor_id,
            bme280_address=args.bme280_address,
            veml7700_address=args.veml7700_address,
            ads1115_address=args.ads1115_address,
            soil_channel=args.soil_channel,
        )

    except Exception:
        LOGGER.exception(
            "sensor subsystem initialization failed; "
            "image capture remains enabled"
        )

        return None


def main() -> None:

    args = parse_args()

    if args.interval_seconds < 60:
        raise SystemExit(
            "--interval-seconds must be at least 60"
        )

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )

    args.data_directory.mkdir(
        parents=True,
        exist_ok=True,
    )

    queue = CaptureQueue(
        args.data_directory / "capture-queue.db"
    )

    queue.initialize()

    uploader = CaptureUploader(
        queue,
        args.server_url,
    )

    sensor_manager = build_sensor_manager(
        args
    )

    while True:

        try:
            run_cycle(
                queue,
                uploader,
                args.tray_code,
                args.timezone,
                args.data_directory / "captures",
                sensor_manager=sensor_manager,
            )

        except Exception:
            LOGGER.exception(
                "capture cycle failed"
            )

            if args.once:
                raise

        if args.once:
            break

        time.sleep(
            args.interval_seconds
        )


if __name__ == "__main__":
    main()
