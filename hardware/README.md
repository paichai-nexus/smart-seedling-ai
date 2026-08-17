# Hardware baseline

The P1 baseline is three independent fixed-camera capture stations plus shared
lab tools. Procurement follows two controlled sources:

- `Paichai_NEXUS_Smart_Seedling_AI_BOM_v1.1.xlsx` — quantities, ownership,
  acceptance gates, and editable procurement prices;
- `Datasheet_Manifest_v1.md` — official manufacturer or module-vendor sources.

## P1 station

Each station uses Raspberry Pi 5, Camera Module 3 Standard, BME280 temperature
and humidity sensing, VEML7700 illuminance sensing, ADS1115 ADC, and two SEN0193
capacitive soil-moisture sensors. The fixed rig, high-CRI flicker-free lighting,
diffuser, and metric/ArUco target are measurement equipment, not presentation
accessories.

Software must retain BME280 pressure, SEN0193 raw ADC/voltage, sensor identity,
timezone-aware timestamps, and calibration provenance. SEN0193 readings are
relative measurements and must not be described as research-grade absolute VWC.

## Safety boundary

Pumps, relays, solenoids, fertilizer or pesticide dosing hardware, hobby pH/EC
probes, and drones are excluded from P1. They require a separately reviewed
phase after the fixed-camera 14-day pilot.

## Build order

Follow the `Build_Acceptance` sheet from G0 through G9. A failed gate blocks its
downstream stages; YOLO-Seg is a G9 go/no-go decision after the OpenCV baseline
has a held-out expert-mask error report.
