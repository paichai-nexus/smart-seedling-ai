# Smart Seedling AI — Datasheet Manifest v1

기준일: 2026-08-17  
대상: Pai Chai NEXUS / `paichai-nexus/smart-seedling-ai`

> 원칙: 제조사 또는 공식 모듈 벤더 문서를 우선 사용한다.  
> 칩 데이터시트와 breakout/module 보드 사양은 서로 다른 문서로 관리한다.

## P1 Core / Vision

| Item | Selected model | Official source | 기존 파일 조치 |
|---|---|---|---|
| Raspberry Pi 5 4GB | Raspberry Pi 5 4GB | https://pip-assets.raspberrypi.com/categories/892-raspberry-pi-5/documents/RP-008348-DS-6-raspberry-pi-5-product-brief.pdf | CM4 PDF 삭제/교체 |
| 27W PSU | Raspberry Pi 27W USB-C PSU | https://pip-assets.raspberrypi.com/categories/898-raspberry-pi-27w-usb-c-power-supply/documents/RP-008245-DS-1-27w-usb-c-power-supply-product-brief.pdf | 유지 |
| Active Cooler | Raspberry Pi Active Cooler for Pi 5 | https://pip-assets.raspberrypi.com/categories/993-raspberry-pi-active-cooler/documents/RP-008188-DS-2-raspberry-pi-active-cooler-product-brief.pdf | CM5 cooler PDF 삭제/교체 |
| Camera Module 3 | Standard | https://pip-assets.raspberrypi.com/categories/786-raspberry-pi-camera-module-3/documents/RP-008151-DS-1-camera-module-3-product-brief.pdf | 유지 |
| Camera Cable | Standard–Mini 500mm | https://www.raspberrypi.com/products/camera-cable/?variant=camera-cable-std-mini-500 | CM5 PDF 삭제/교체 |
| microSD | Raspberry Pi 128GB A2 | https://datasheets.raspberrypi.com/sd-card/sd-card-product-brief.pdf | 구매 모델 확정 |

## P1 Sensors

| Item | Selected model | Chip datasheet | Module / board source |
|---|---|---|---|
| Temp/RH | DFRobot SEN0236 BME280 | https://www.bosch-sensortec.com/media/boschsensortec/downloads/datasheets/bst-bme280-ds002.pdf | https://wiki.dfrobot.com/sen0236/ |
| Illuminance | DFRobot SEN0228 VEML7700 | https://www.vishay.com/docs/84286/veml7700.pdf | https://wiki.dfrobot.com/sen0228/ |
| ADC | DFRobot DFR0553 ADS1115 | https://www.ti.com/lit/gpn/ADS1115 | https://wiki.dfrobot.com/dfr0553/ |
| Soil moisture | DFRobot SEN0193 | schematic: https://dfimg.dfrobot.com/wiki/17627/SEN0193_capacitive-soil-moisture-sensor_schematics_1.0.pdf | https://wiki.dfrobot.com/sen0193/ |

### Module schematics

- SEN0236 BME280 board schematic:  
  https://dfimg.dfrobot.com/wiki/18542/SEN0236_gravity-bme280-environmental-sensor_schematics_v1.0.pdf
- SEN0228 VEML7700 board schematic:  
  https://dfimg.dfrobot.com/wiki/17551/SEN0228_veml7700-ambient-light-sensor_schematics_V1.0.pdf
- DFR0553 ADS1115 board schematic:  
  https://dfimg.dfrobot.com/wiki/19356/DFR0553_gravity-ads1115-16-big-adc-module_schematics_V1.0.pdf

## P1 Optics / Calibration

### Lighting reference

Reference specification:
- Waveform Lighting CENTRIC DAYLIGHT 95 CRI T5
- 5000K, 2-ft, PN `4026.50.2F`
- CRI 95+, flicker-free, 9W / 900 lm

Product:
https://store.waveformlighting.com/products/centric-daylight-95-cri-t5-led-linear-light-fixture

Specification sheet:
https://store.waveformlighting.com/cdn/shop/files/CENTRIC_DAYLIGHT_95_CRI_T5_LED_Linear_Light_Fixture_Specification_Sheet.pdf?v=8230845690346122601

한국에서 실제 발주할 때는 **KC 인증 + 5000K 고정 + CRI 95 이상 + flicker-free**를 만족하는 국내 동급 선형 조명을 우선 검토한다.

### Color reference

Calibrite ColorChecker Classic Mini `CCC-MINI`:
https://calibrite.com/ko/product/colorchecker-classic-mini/?noredirect=ko-KR

### Metric calibration

`pixels_per_cm` 산출용 기준판은 자체 제작:
- ArUco marker
- 실제 길이가 검증된 metric scale
- 무광 rigid board
- tray plane과 동일 평면에 배치

## P2 Reference Sensor

Sensirion SHT45:
- Product: https://sensirion.com/products/catalog/SHT45
- Datasheet: https://sensirion.com/media/documents/33FD6951/67EB9032/HT_DS_Datasheet_SHT4x_5.pdf

P1 station마다 살 필요는 없고, station 간 BME280 편차를 확인하는 공용 reference sensor 후보로 사용한다.

## 아직 벤더를 고정하지 않는 항목

다음은 트레이 규격과 실험 환경이 정해진 뒤 구매 모델을 확정한다.

- 2020 aluminum extrusion rig
- opal PMMA / polycarbonate diffuser
- camera fixed plate
- enclosure
- CAT6 / switch
- multimeter / soldering / crimp tools
- research-grade VWC/EC sensor

이 항목은 특정 제품을 고르기 전까지 임의의 데이터시트를 붙이지 않는다.

## 구매하지 않는 P1 항목

- pump
- relay
- solenoid
- fertilizer/pesticide dosing hardware
- drone
- pH/EC hobby probe

측정 플랫폼과 14-day pilot이 검증된 뒤 P2/P3에서 결정한다.
