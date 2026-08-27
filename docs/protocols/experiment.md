# Seedling Image Experiment Protocol

## Experimental Unit

A seedling identified by a stable tray-cell coordinate.

## Initial Experiment

- one crop
- one tray geometry
- fixed camera position
- fixed illumination
- daily capture
- minimum 14-day observation period

## Capture Metadata

Each image should retain:

- timestamp
- tray ID
- cell ID
- camera configuration
- scale calibration
- capture profile
- environmental context when available

## Annotation

Annotators should label:

- visible plant mask
- yellowing
- visible spots
- visible damage
- uncertain observations

Uncertain biological interpretation must be sent to expert review.

## Dataset Split

Split by tray or cultivation batch rather than by individual image.

Recommended initial split:

- 70% train/development
- 15% validation
- 15% held-out test

## Reporting

Report metrics:

- per image
- per seedling
- per cultivation batch
- per capture day

Representative failure examples must be preserved with the quantitative results.
