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


@dataclass(frozen=True)
class TrayCell:
    row: int
    column: int
    image: np.ndarray


@dataclass(frozen=True)
class CaptureQuality:
    accepted: bool
    blur_score: float
    mean_brightness: float
    dark_pixel_ratio: float
    bright_pixel_ratio: float
    reasons: tuple[str, ...]


@dataclass(frozen=True)
class TrayRectification:
    image: np.ndarray
    corners: tuple[tuple[float, float], ...]
    source_area_ratio: float


def decode_image(content: bytes) -> np.ndarray:
    encoded = np.frombuffer(content, dtype=np.uint8)
    image = cv2.imdecode(encoded, cv2.IMREAD_COLOR)
    if image is None:
        raise ValueError("The uploaded file is not a decodable image")
    return image


def assess_capture_quality(
    image: np.ndarray,
    minimum_blur_score: float = 40.0,
    minimum_brightness: float = 35.0,
    maximum_brightness: float = 220.0,
    maximum_clipped_ratio: float = 0.35,
) -> CaptureQuality:
    """Evaluate whether a fixed-camera image is usable for measurement."""
    if image.ndim != 3 or image.shape[2] != 3:
        raise ValueError("A three-channel BGR image is required")
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    blur_score = float(cv2.Laplacian(gray, cv2.CV_64F).var())
    mean_brightness = float(gray.mean())
    dark_ratio = float(np.mean(gray <= 5))
    bright_ratio = float(np.mean(gray >= 250))

    reasons = []
    if blur_score < minimum_blur_score:
        reasons.append("image_too_blurry")
    if mean_brightness < minimum_brightness:
        reasons.append("image_too_dark")
    if mean_brightness > maximum_brightness:
        reasons.append("image_too_bright")
    if dark_ratio > maximum_clipped_ratio:
        reasons.append("excessive_black_clipping")
    if bright_ratio > maximum_clipped_ratio:
        reasons.append("excessive_white_clipping")

    return CaptureQuality(
        accepted=not reasons,
        blur_score=round(blur_score, 2),
        mean_brightness=round(mean_brightness, 2),
        dark_pixel_ratio=round(dark_ratio, 4),
        bright_pixel_ratio=round(bright_ratio, 4),
        reasons=tuple(reasons),
    )


def _ordered_quad(points: np.ndarray) -> np.ndarray:
    points = points.reshape(4, 2).astype(np.float32)
    coordinate_sum = points.sum(axis=1)
    coordinate_difference = np.diff(points, axis=1).reshape(-1)
    return np.array(
        [
            points[np.argmin(coordinate_sum)],
            points[np.argmin(coordinate_difference)],
            points[np.argmax(coordinate_sum)],
            points[np.argmax(coordinate_difference)],
        ],
        dtype=np.float32,
    )


def detect_and_rectify_tray(
    image: np.ndarray,
    minimum_area_ratio: float = 0.25,
) -> TrayRectification:
    """Detect the dominant quadrilateral and warp it to a top-down view."""
    if not 0 < minimum_area_ratio < 1:
        raise ValueError("minimum_area_ratio must be between 0 and 1")
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)
    edges = cv2.Canny(blurred, 40, 120)
    edges = cv2.morphologyEx(edges, cv2.MORPH_CLOSE, np.ones((5, 5), np.uint8))
    contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    image_area = image.shape[0] * image.shape[1]

    candidates = []
    for contour in contours:
        perimeter = cv2.arcLength(contour, True)
        polygon = cv2.approxPolyDP(contour, 0.02 * perimeter, True)
        if len(polygon) == 4 and cv2.isContourConvex(polygon):
            area_ratio = cv2.contourArea(polygon) / image_area
            if area_ratio >= minimum_area_ratio:
                candidates.append((area_ratio, polygon))
    if not candidates:
        raise ValueError("tray_boundary_not_found")

    area_ratio, polygon = max(candidates, key=lambda item: item[0])
    corners = _ordered_quad(polygon)
    top_left, top_right, bottom_right, bottom_left = corners
    width = max(
        np.linalg.norm(bottom_right - bottom_left),
        np.linalg.norm(top_right - top_left),
    )
    height = max(
        np.linalg.norm(top_right - bottom_right),
        np.linalg.norm(top_left - bottom_left),
    )
    output_width, output_height = max(round(width), 2), max(round(height), 2)
    destination = np.array(
        [
            [0, 0],
            [output_width - 1, 0],
            [output_width - 1, output_height - 1],
            [0, output_height - 1],
        ],
        dtype=np.float32,
    )
    transform = cv2.getPerspectiveTransform(corners, destination)
    rectified = cv2.warpPerspective(image, transform, (output_width, output_height))
    normalized_corners = tuple(
        (round(float(x) / image.shape[1], 4), round(float(y) / image.shape[0], 4))
        for x, y in corners
    )
    return TrayRectification(
        image=rectified,
        corners=normalized_corners,
        source_area_ratio=round(float(area_ratio), 4),
    )


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


def split_tray_grid(
    image: np.ndarray,
    rows: int,
    columns: int,
    margin_ratio: float = 0.08,
) -> list[TrayCell]:
    """Split a rectified tray image into stable cells with an inner margin."""
    if rows < 1 or columns < 1:
        raise ValueError("rows and columns must be positive")
    if not 0 <= margin_ratio < 0.4:
        raise ValueError("margin_ratio must be between 0 and 0.4")
    height, width = image.shape[:2]
    if height < rows or width < columns:
        raise ValueError("image is smaller than the requested tray grid")

    cells = []
    for row in range(rows):
        y0, y1 = round(row * height / rows), round((row + 1) * height / rows)
        for column in range(columns):
            x0, x1 = round(column * width / columns), round((column + 1) * width / columns)
            x_margin = round((x1 - x0) * margin_ratio)
            y_margin = round((y1 - y0) * margin_ratio)
            crop = image[y0 + y_margin : y1 - y_margin, x0 + x_margin : x1 - x_margin]
            cells.append(TrayCell(row=row + 1, column=column + 1, image=crop))
    return cells
