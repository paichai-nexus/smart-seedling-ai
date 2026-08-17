from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np


@dataclass(frozen=True)
class LeafAnalysis:
    leaf_area_cm2: float
    green_pixel_count: int
    image_pixel_count: int
    coverage_ratio: float
    confidence: float


def decode_image(content: bytes) -> np.ndarray:
    encoded = np.frombuffer(content, dtype=np.uint8)
    image = cv2.imdecode(encoded, cv2.IMREAD_COLOR)
    if image is None:
        raise ValueError("The uploaded file is not a decodable image")
    return image


def analyze_green_leaf_area(image: np.ndarray, pixels_per_cm: float) -> LeafAnalysis:
    """Measure green projected area under a fixed, calibrated capture setup.

    This HSV baseline is intentionally auditable. It is a reference method for
    controlled images, not a general plant detector or disease diagnosis.
    """
    if pixels_per_cm <= 0:
        raise ValueError("pixels_per_cm must be positive")
    if image.ndim != 3 or image.shape[2] != 3:
        raise ValueError("A three-channel BGR image is required")

    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    mask = cv2.inRange(hsv, np.array([25, 35, 25]), np.array([95, 255, 255]))
    kernel = np.ones((3, 3), np.uint8)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)

    green_pixels = int(cv2.countNonZero(mask))
    image_pixels = int(mask.size)
    area_cm2 = green_pixels / (pixels_per_cm**2)
    coverage = green_pixels / image_pixels

    # Confidence describes capture usefulness, not biological certainty.
    confidence = 0.95 if 0.01 <= coverage <= 0.85 else 0.55
    return LeafAnalysis(
        leaf_area_cm2=round(area_cm2, 3),
        green_pixel_count=green_pixels,
        image_pixel_count=image_pixels,
        coverage_ratio=round(coverage, 4),
        confidence=confidence,
    )
