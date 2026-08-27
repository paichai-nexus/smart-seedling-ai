from __future__ import annotations

from dataclasses import dataclass

from edge.sensors.ads1115 import ADS1115Reader


@dataclass(frozen=True)
class SoilMoistureReading:
    raw_adc: int
    voltage_v: float


class SoilMoistureSensor:
    """SEN0193 reader preserving raw ADC data for calibration."""

    def __init__(
        self,
        adc: ADS1115Reader,
        channel: int = 0,
    ) -> None:
        if not 0 <= channel <= 3:
            raise ValueError(
                "soil moisture ADC channel must be between 0 and 3"
            )

        self._adc = adc
        self.channel = channel

    def read(self) -> SoilMoistureReading:
        reading = self._adc.read_channel(
            self.channel
        )

        return SoilMoistureReading(
            raw_adc=reading.raw_adc,
            voltage_v=reading.voltage_v,
        )
