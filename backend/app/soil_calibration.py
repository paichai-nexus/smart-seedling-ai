from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SoilMoistureEstimate:
    relative_percent: float
    out_of_calibration_range: bool


def relative_soil_moisture(raw_adc: int, dry_adc: int, wet_adc: int) -> SoilMoistureEstimate:
    """Map dry/wet reference counts to a clamped relative percentage.

    This calculation is a sensor-specific relative index, never absolute VWC.
    """
    if not 0 <= raw_adc <= 32767:
        raise ValueError("raw_adc must be between 0 and 32767")
    if not 0 <= dry_adc <= 32767 or not 0 <= wet_adc <= 32767:
        raise ValueError("calibration ADC values must be between 0 and 32767")
    if dry_adc == wet_adc:
        raise ValueError("dry_adc and wet_adc must differ")

    relative = ((raw_adc - dry_adc) / (wet_adc - dry_adc)) * 100
    out_of_range = relative < 0 or relative > 100
    return SoilMoistureEstimate(
        relative_percent=round(min(max(relative, 0), 100), 2),
        out_of_calibration_range=out_of_range,
    )
