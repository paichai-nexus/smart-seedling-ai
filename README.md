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
