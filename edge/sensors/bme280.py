from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class BME280Reading:
    temperature_c: float
    pressure_hpa: float
    humidity_percent: float


class BME280Sensor:
    """Thin wrapper around the CircuitPython BME280 driver."""

    def __init__(self, i2c: Any, address: int = 0x77) -> None:
        from adafruit_bme280 import basic as adafruit_bme280

        self.address = address
        self._sensor = adafruit_bme280.Adafruit_BME280_I2C(
            i2c,
            address=address,
        )

    def read(self) -> BME280Reading:
        return BME280Reading(
            temperature_c=float(self._sensor.temperature),
            pressure_hpa=float(self._sensor.pressure),
            humidity_percent=float(self._sensor.relative_humidity),
        )
