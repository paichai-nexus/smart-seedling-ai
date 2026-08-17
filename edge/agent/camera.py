from __future__ import annotations

import subprocess
from datetime import datetime
from pathlib import Path


def capture_image(output_directory: str | Path, captured_at: datetime) -> Path:
    if captured_at.tzinfo is None or captured_at.utcoffset() is None:
        raise ValueError("captured_at must include a timezone offset")
    directory = Path(output_directory)
    directory.mkdir(parents=True, exist_ok=True)
    destination = directory / f"{captured_at.strftime('%Y%m%dT%H%M%S%z')}.jpg"
    subprocess.run(
        [
            "rpicam-still",
            "--nopreview",
            "--immediate",
            "--quality",
            "95",
            "--output",
            str(destination),
        ],
        check=True,
    )
    return destination
