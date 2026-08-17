from __future__ import annotations

import logging
from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Any, Optional

import httpx

from edge.sensors.ads1115 import ADS1115Reader
from edge.sensors.bme280 import BME280Sensor
from edge.sensors.soil_moisture import SoilMoistureSensor
from edge.sensors.veml7700 import VEML7700Sensor


LOGGER = logging.getLogger(
    "smart-seedling-edge.sensors"
)


@dataclass(frozen=True)
class SensorSnapshot:
    measured_at: datetime
    source: str
    sensor_id: str

    temperature_c: Optional[float] = None
    pressure_hpa: Optional[float] = None
    humidity_percent: Optional[float] = None

    soil_moisture_raw_adc: Optional[int] = None
    soil_moisture_voltage_v: Optional[float] = None

    illuminance_lux: Optional[float] = None

    def to_payload(self) -> dict[str, Any]:
        if (
            self.measured_at.tzinfo is None
            or self.measured_at.utcoffset() is None
        ):
            raise ValueError(
                "measured_at must include a timezone offset"
            )

        payload = asdict(self)
        payload["measured_at"] = (
            self.measured_at.isoformat()
        )

        return {
            key: value
            for key, value in payload.items()
            if value is not None
        }


class SensorManager:
    def __init__(
        self,
        server_url: str,
        tray_code: str,
        source: str,
        sensor_id: str,
        bme280: Optional[BME280Sensor],
        veml7700: Optional[VEML7700Sensor],
        soil_moisture: Optional[SoilMoistureSensor],
        client: Optional[httpx.Client] = None,
    ) -> None:

        self.server_url = server_url.rstrip("/")
        self.tray_code = tray_code.upper()

        self.source = source
        self.sensor_id = sensor_id

        self.bme280 = bme280
        self.veml7700 = veml7700
        self.soil_moisture = soil_moisture

        self.client = (
            client
            or httpx.Client(timeout=15)
        )

    @classmethod
    def from_hardware(
        cls,
        server_url: str,
        tray_code: str,
        source: str = "raspberry-pi-edge",
        sensor_id: str = "seedling-node-01",
        bme280_address: int = 0x77,
        veml7700_address: int = 0x10,
        ads1115_address: int = 0x48,
        soil_channel: int = 0,
        ads1115_gain: float = 1.0,
    ) -> "SensorManager":

        try:
            import board
        except ImportError as exc:
            raise RuntimeError(
                "Adafruit Blinka is required on the Raspberry Pi"
            ) from exc

        i2c = board.I2C()

        bme280 = None
        veml7700 = None
        soil_moisture = None

        try:
            bme280 = BME280Sensor(
                i2c,
                address=bme280_address,
            )
        except Exception:
            LOGGER.exception(
                "BME280 initialization failed at 0x%02X",
                bme280_address,
            )

        try:
            veml7700 = VEML7700Sensor(
                i2c,
                address=veml7700_address,
            )
        except Exception:
            LOGGER.exception(
                "VEML7700 initialization failed at 0x%02X",
                veml7700_address,
            )

        try:
            adc = ADS1115Reader(
                i2c,
                address=ads1115_address,
                gain=ads1115_gain,
            )

            soil_moisture = SoilMoistureSensor(
                adc,
                channel=soil_channel,
            )

        except Exception:
            LOGGER.exception(
                "ADS1115/SEN0193 initialization failed at 0x%02X",
                ads1115_address,
            )

        if (
            bme280 is None
            and veml7700 is None
            and soil_moisture is None
        ):
            raise RuntimeError(
                "no environmental sensor could be initialized"
            )

        return cls(
            server_url=server_url,
            tray_code=tray_code,
            source=source,
            sensor_id=sensor_id,
            bme280=bme280,
            veml7700=veml7700,
            soil_moisture=soil_moisture,
        )

    def read_snapshot(
        self,
        measured_at: datetime,
    ) -> SensorSnapshot:

        values: dict[str, Any] = {}

        if self.bme280 is not None:
            try:
                reading = self.bme280.read()

                values.update(
                    temperature_c=reading.temperature_c,
                    pressure_hpa=reading.pressure_hpa,
                    humidity_percent=reading.humidity_percent,
                )

            except Exception:
                LOGGER.exception(
                    "BME280 read failed"
                )

        if self.veml7700 is not None:
            try:
                reading = self.veml7700.read()

                values["illuminance_lux"] = (
                    reading.illuminance_lux
                )

            except Exception:
                LOGGER.exception(
                    "VEML7700 read failed"
                )

        if self.soil_moisture is not None:
            try:
                reading = self.soil_moisture.read()

                values.update(
                    soil_moisture_raw_adc=reading.raw_adc,
                    soil_moisture_voltage_v=reading.voltage_v,
                )

            except Exception:
                LOGGER.exception(
                    "SEN0193 read failed"
                )

        if not values:
            raise RuntimeError(
                "all environmental sensor reads failed"
            )

        return SensorSnapshot(
            measured_at=measured_at,
            source=self.source,
            sensor_id=self.sensor_id,
            **values,
        )

    def upload(
        self,
        snapshot: SensorSnapshot,
    ) -> dict[str, Any]:

        response = self.client.post(
            (
                f"{self.server_url}/api/v1/trays/"
                f"{self.tray_code}/sensor-readings"
            ),
            json=snapshot.to_payload(),
        )

        response.raise_for_status()

        return response.json()

    def read_and_upload(
        self,
        measured_at: datetime,
    ) -> dict[str, Any]:

        snapshot = self.read_snapshot(
            measured_at
        )

        return self.upload(snapshot)
