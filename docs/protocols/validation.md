# Vision Baseline Validation Plan

## Objective

Evaluate the OpenCV HSV-based projected leaf-area measurement baseline under controlled capture conditions before introducing learned segmentation models.

## Research Question

Can a calibrated HSV segmentation pipeline provide sufficiently stable projected leaf-area measurements for longitudinal seedling monitoring?

## Baseline

The initial baseline uses:

- fixed RGB camera
- fixed camera height and focal length
- controlled illumination
- perspective rectification
- tray-cell coordinates
- HSV-based green-region segmentation

## Ground Truth

Expert-reviewed manual plant masks will be used as the reference.

Successive images from the same seedling must not be split across training and evaluation groups.

## Evaluation Metrics

- MAE
- MAPE
- IoU
- Dice coefficient
- failure rate
- capture rejection rate

## Failure Cases

Record failures caused by:

- illumination variation
- shadows
- blur
- overexposure
- underexposure
- perspective distortion
- overlapping leaves
- background color leakage

## Decision Rule

YOLO segmentation or another learned model should only be introduced when the classical baseline shows a measurable limitation that a learned model can reasonably address.

Complexity alone is not considered an improvement.
