import unittest

import cv2
import numpy as np
from app.vision import analyze_green_leaf_area, decode_image, split_tray_grid


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
