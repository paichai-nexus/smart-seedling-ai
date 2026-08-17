from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class VEML7700Reading:
    illuminance_lux: float


class VEML7700Sensor:
    """Ambient-light reader using VEML7700 auto-ranging lux mode."""

    def __init__(self, i2c: Any, address: int = 0x10) -> None:
        import adafruit_veml7700

        self.address = address
        self._sensor = adafruit_veml7700.VEML7700(
            i2c,
            address=address,
        )

    def read(self) -> VEML7700Reading:
        return VEML7700Reading(
            illuminance_lux=max(
                0.0,
                float(self._sensor.autolux),
            )
        )
