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
```

## Next development milestone

1. Confirm target crop and tray geometry with the horticulture advisor.
2. Build a fixed camera rig and collect a color/scale reference image.
3. Replace manually submitted metrics with an OpenCV segmentation baseline.
4. Validate leaf-area error against manually annotated masks.
5. Add YOLO segmentation only after the baseline dataset is reviewed.
