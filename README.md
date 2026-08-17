# Smart Seedling AI

Vision AI, environmental sensors, and horticultural expertise combined into a
research platform for individual seedling growth monitoring.

> The system observes plant condition and flags visual anomalies. Biological
> diagnosis and treatment decisions remain with horticultural experts and
> require supporting measurements.

## MVP scope

The first vertical slice provides:

- stable seedling IDs based on tray cell coordinates;
- time-series observations for leaf area, discoloration, and sensor readings;
- growth-rate and relative-growth calculations;
- conservative `healthy`, `warning`, and `expert_review` status assignment;
- calibrated JPEG/PNG upload with an auditable OpenCV HSV leaf-area baseline;
- a FastAPI service with SQLite persistence and a simple research dashboard.

## Quick start

Requires Python 3.9 or newer.

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
uvicorn app.main:app --app-dir backend --reload
```

Open `http://127.0.0.1:8000/docs` for the API and
`http://127.0.0.1:8000/dashboard` for the dashboard.

The image endpoint requires a measured `pixels_per_cm` value from the fixed
camera setup. This converts projected green pixels to square centimetres; it is
not a biological diagnosis. Use `POST /api/v1/images/analyze` in the API docs to
upload a JPEG or PNG and create the corresponding observation.

For a rectified full-tray capture, use
`POST /api/v1/trays/{tray_code}/images/analyze`. The endpoint reads the tray's
stored row/column geometry, removes a configurable inner cell margin, analyzes
every cell in row-major order, and persists one time-series observation per
seedling. This fixed-grid method assumes the tray boundary is aligned with the
image; perspective rectification is the next capture-quality milestone.

Every image passes a capture-quality gate before persistence. The gate reports
blur score, mean brightness, and black/white clipping ratios. Rejected captures
return actionable reason codes such as `image_too_blurry` or `image_too_dark`
and do not create research observations.

Full-tray uploads can set `rectify=true` to detect the dominant quadrilateral
tray boundary and apply a top-down perspective transform before grid splitting.
The normalized source corners and detected area ratio are returned for audit.
If boundary detection is unreliable, the API rejects the capture instead of
silently assigning seedlings to the wrong cells.

Environmental measurements are ingested with
`POST /api/v1/trays/{tray_code}/sensor-readings` and read back as a latest-first
time series. Temperature, humidity, soil moisture, illuminance, EC, and pH are
nullable independently so an inexpensive edge node can report only the sensors
it actually has. Timestamps must include a timezone offset and duplicate
tray/time/source readings are rejected.

When a full-tray image is analyzed, the service links the temporally nearest
sensor reading from the same tray within a configurable window (30 minutes by
default). The immutable link stores the absolute time difference, allowing
research exports to combine visual growth measurements with their environmental
context without silently joining distant measurements.

Observations classified as `warning` or `expert_review` enter an expert review
queue. A review records observable evidence separately from possible causes.
Knowledge rules follow a draft-and-approve workflow: unapproved rules are hidden
from the default recommendation query, and the schema intentionally contains no
autonomous fertilizer or pesticide dosage field.

`GET /api/v1/observations/{observation_id}/recommendations` translates measured
ratios and growth change into auditable signals, currently `discoloration`,
`damage`, `growth_decline`, `growth_slowdown`, and `low_confidence`. It ranks
approved rules by signal coverage and returns possible causes, required checks,
safe actions, approval provenance, and an explicit non-diagnostic disclaimer.

Controlled experiments contain at least one control and one treatment group,
with each tray assigned to only one group per experiment. The experiment CSV
export produces one row per seedling observation and includes group identity,
Vision metrics, linked sensor context, and the latest expert assessment. Records
outside the declared experiment period are excluded using timezone-aware times.

The experiment comparison endpoint calculates each seedling's relative change
between its first and last valid observation, then reports group sample size,
mean, median, population standard deviation, minimum, and maximum. These are
descriptive statistics; the dashboard explicitly avoids claiming significance
or causality.

Each tray can store a fixed-camera capture profile containing scale calibration,
cell margin, perspective-rectification settings, and the allowed sensor matching
window. Profile changes retain an operator and timezone-aware update timestamp
so measurement configuration remains auditable.

The full-tray analysis endpoint uses the stored profile whenever form settings
are omitted. Explicit request values can override individual profile fields, and
the response reports the effective settings plus whether they came from the
profile, the request, or a mixture of both.

Run tests:

```bash
python -m unittest discover -s backend/tests -v
```

## Repository layout

```text
backend/app/       API, domain rules, and SQLite repository
backend/tests/     dependency-free domain tests
frontend/          static research dashboard
docs/              architecture and research protocol
hardware/          BOM, official datasheet manifest, and hardware baseline
```

## Hardware references

- [Hardware baseline](hardware/README.md)
- [Official datasheet manifest](hardware/Datasheet_Manifest_v1.md)
- [Editable BOM](hardware/Paichai_NEXUS_Smart_Seedling_AI_BOM_v1.1.xlsx)

## Next development milestone

1. Confirm target crop and tray geometry with the horticulture advisor.
2. Build a fixed camera rig and collect a color/scale reference image.
3. Replace manually submitted metrics with an OpenCV segmentation baseline.
4. Validate leaf-area error against manually annotated masks.
5. Add YOLO segmentation only after the baseline dataset is reviewed.
