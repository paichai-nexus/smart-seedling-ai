from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class SegmentationMetrics:
    intersection: int
    union: int
    predicted_area: int
    ground_truth_area: int
    iou: float
    dice: float
    area_absolute_error: int
    area_percentage_error: float | None


def evaluate_binary_masks(
    predicted_mask: np.ndarray,
    ground_truth_mask: np.ndarray,
) -> SegmentationMetrics:
    if predicted_mask.shape != ground_truth_mask.shape:
        raise ValueError(
            f"Mask shape mismatch: predicted={predicted_mask.shape}, "
            f"ground_truth={ground_truth_mask.shape}"
        )

    pred = predicted_mask.astype(bool)
    truth = ground_truth_mask.astype(bool)

    intersection = int(np.logical_and(pred, truth).sum())
    union = int(np.logical_or(pred, truth).sum())

    predicted_area = int(pred.sum())
    ground_truth_area = int(truth.sum())

    iou = intersection / union if union else 1.0

    denominator = predicted_area + ground_truth_area
    dice = (
        (2.0 * intersection) / denominator
        if denominator
        else 1.0
    )

    area_absolute_error = abs(predicted_area - ground_truth_area)

    area_percentage_error = (
        area_absolute_error / ground_truth_area * 100.0
        if ground_truth_area
        else None
    )

    return SegmentationMetrics(
        intersection=intersection,
        union=union,
        predicted_area=predicted_area,
        ground_truth_area=ground_truth_area,
        iou=iou,
        dice=dice,
        area_absolute_error=area_absolute_error,
        area_percentage_error=area_percentage_error,
    )
