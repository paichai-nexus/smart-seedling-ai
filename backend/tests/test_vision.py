import unittest

import cv2
import numpy as np
from app.vision import (
    analyze_green_leaf_area,
    assess_capture_quality,
    decode_image,
    detect_and_rectify_tray,
    split_tray_grid,
)


class VisionTests(unittest.TestCase):
    def test_green_area_uses_camera_calibration(self):
        image = np.zeros((100, 100, 3), dtype=np.uint8)
        image[20:80, 30:70] = (0, 180, 0)

        result = analyze_green_leaf_area(image, pixels_per_cm=10)

        self.assertAlmostEqual(result.leaf_area_cm2, 24.0, delta=0.1)
        self.assertAlmostEqual(result.coverage_ratio, 0.24, delta=0.01)
        self.assertEqual(result.confidence, 0.95)

    def test_encoded_png_is_decoded(self):
        source = np.zeros((12, 8, 3), dtype=np.uint8)
        success, encoded = cv2.imencode(".png", source)
        self.assertTrue(success)
        self.assertEqual(decode_image(encoded.tobytes()).shape, (12, 8, 3))

    def test_invalid_bytes_are_rejected(self):
        with self.assertRaises(ValueError):
            decode_image(b"not an image")

    def test_sharp_balanced_capture_passes_quality_gate(self):
        image = np.full((100, 100, 3), 90, dtype=np.uint8)
        image[::10, :] = 120
        image[:, ::10] = 120
        image[20:80, 30:70] = (0, 180, 0)
        quality = assess_capture_quality(image)
        self.assertTrue(quality.accepted)
        self.assertEqual(quality.reasons, ())

    def test_dark_uniform_capture_reports_actionable_reasons(self):
        image = np.zeros((100, 100, 3), dtype=np.uint8)
        quality = assess_capture_quality(image)
        self.assertFalse(quality.accepted)
        self.assertIn("image_too_blurry", quality.reasons)
        self.assertIn("image_too_dark", quality.reasons)
        self.assertIn("excessive_black_clipping", quality.reasons)

    def test_perspective_tray_is_rectified_to_top_down_view(self):
        image = np.zeros((300, 400, 3), dtype=np.uint8)
        polygon = np.array([[80, 40], [340, 70], [310, 260], [50, 230]], dtype=np.int32)
        cv2.fillConvexPoly(image, polygon, (150, 150, 150))
        cv2.polylines(image, [polygon], True, (255, 255, 255), 5)

        result = detect_and_rectify_tray(image)

        self.assertGreater(result.source_area_ratio, 0.35)
        self.assertEqual(len(result.corners), 4)
        self.assertGreater(result.image.shape[1], result.image.shape[0])

    def test_missing_tray_boundary_is_rejected(self):
        image = np.full((200, 200, 3), 100, dtype=np.uint8)
        with self.assertRaisesRegex(ValueError, "tray_boundary_not_found"):
            detect_and_rectify_tray(image)

    def test_tray_grid_uses_one_based_row_major_cells(self):
        image = np.zeros((100, 200, 3), dtype=np.uint8)
        cells = split_tray_grid(image, rows=2, columns=4, margin_ratio=0)

        self.assertEqual(len(cells), 8)
        self.assertEqual((cells[0].row, cells[0].column), (1, 1))
        self.assertEqual((cells[-1].row, cells[-1].column), (2, 4))
        self.assertEqual(cells[0].image.shape, (50, 50, 3))

    def test_tray_grid_margin_removes_cell_edges(self):
        image = np.zeros((100, 100, 3), dtype=np.uint8)
        cell = split_tray_grid(image, rows=1, columns=1, margin_ratio=0.1)[0]
        self.assertEqual(cell.image.shape, (80, 80, 3))
