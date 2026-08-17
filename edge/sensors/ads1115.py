from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ADCReading:
    raw_adc: int
    voltage_v: float


_FULL_SCALE_BY_GAIN = {
    2 / 3: 6.144,
    1.0: 4.096,
    2.0: 2.048,
    4.0: 1.024,
    8.0: 0.512,
    16.0: 0.256,
}


class ADS1115Reader:
    """Read signed ADS1115 counts and convert them to volts."""

    def __init__(
        self,
        i2c: Any,
        address: int = 0x48,
        gain: float = 1.0,
    ) -> None:
        from adafruit_ads1x15 import ads1115

        normalized_gain = min(
            _FULL_SCALE_BY_GAIN,
            key=lambda item: abs(item - gain),
        )

        if abs(normalized_gain - gain) > 1e-6:
            raise ValueError(
                f"unsupported ADS1115 gain: {gain}"
            )

        self.address = address
        self.gain = normalized_gain
        self._ads1115 = ads1115
        self._ads = ads1115.ADS1115(
            i2c,
            address=address,
            gain=normalized_gain,
        )

    def read_channel(self, channel: int) -> ADCReading:
        pins = (
            self._ads1115.Pin.A0,
            self._ads1115.Pin.A1,
            self._ads1115.Pin.A2,
            self._ads1115.Pin.A3,
        )

        if not 0 <= channel < len(pins):
            raise ValueError(
                "ADS1115 channel must be between 0 and 3"
            )

        raw_adc = int(
            self._ads.read(pins[channel])
        )

        if raw_adc < 0:
            raise ValueError(
                f"negative single-ended ADC reading ({raw_adc}); "
                "check sensor wiring and ground"
            )

        full_scale_v = _FULL_SCALE_BY_GAIN[self.gain]

        voltage_v = (
            raw_adc
            * full_scale_v
            / 32768.0
        )

        return ADCReading(
            raw_adc=raw_adc,
            voltage_v=voltage_v,
        )
