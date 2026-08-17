# MVP architecture and research boundaries

## Decision record

- **Fixed tray coordinates before ByteTrack:** seedlings remain in known cells, so
  coordinate IDs are cheaper, more stable, and easier to audit than tracking.
- **Classical segmentation baseline before YOLO-seg:** controlled lighting and a
  color reference provide a measurable baseline. A learned model is justified
  only when it reduces held-out leaf-area error.
- **FastAPI + SQLite for MVP:** one service and one file keep deployment on a
  Raspberry Pi simple. PostgreSQL and MQTT become useful when multiple edge
  devices upload concurrently.
- **Triage, not diagnosis:** model output is `healthy`, `warning`, or
  `expert_review`. The knowledge base stores expert-reviewed checks, never an
  autonomous pesticide or fertilizer dose.

## Data flow

```text
Fixed RGB camera + optional sensors
        -> edge capture manifest
        -> quality gate (blur, exposure, reference card)
        -> tray/cell segmentation
        -> per-seedling observation metrics
        -> FastAPI / SQLite
        -> dashboard + expert review queue
```

## First experiment

Select one crop and one tray type. Capture the same tray daily for at least 14
days under fixed camera height, focal length, illumination, and watering-time
offset. Retain raw images and immutable capture metadata.

Primary technical endpoint: mean absolute percentage error of projected leaf
area against expert-reviewed masks. Secondary endpoint: agreement between the
three-level system status and blinded expert assessment. Report per-day and
per-seedling results; never split successive images of the same seedling across
train and test sets.

## Initial annotation protocol

1. Label tray boundary, cell coordinate, and visible plant mask.
2. Add observable attributes only: yellowing, spot, damage, wilt suspicion.
3. Record annotator and reviewer separately.
4. Mark uncertain cases for expert review instead of forcing a class.
5. Split by tray or cultivation batch: 70% train, 15% validation, 15% test.

Start with 500–1,000 controlled images across at least three cultivation batches
for the segmentation feasibility study. This is a planning range, not a claim
of model sufficiency; learning curves determine whether more data is required.

