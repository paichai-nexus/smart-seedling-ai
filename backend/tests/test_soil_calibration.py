import pytest
from app.soil_calibration import relative_soil_moisture


def test_relative_soil_moisture_maps_dry_and_wet_references():
    assert relative_soil_moisture(22000, dry_adc=22000, wet_adc=12000).relative_percent == 0
    assert relative_soil_moisture(12000, dry_adc=22000, wet_adc=12000).relative_percent == 100
    assert relative_soil_moisture(17000, dry_adc=22000, wet_adc=12000).relative_percent == 50


def test_relative_soil_moisture_flags_and_clamps_out_of_range_value():
    result = relative_soil_moisture(10000, dry_adc=22000, wet_adc=12000)
    assert result.relative_percent == 100
    assert result.out_of_calibration_range is True


def test_equal_dry_and_wet_references_are_rejected():
    with pytest.raises(ValueError, match="must differ"):
        relative_soil_moisture(15000, dry_adc=15000, wet_adc=15000)
