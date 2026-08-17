import unittest

import cv2
import numpy as np
from app.vision import analyze_green_leaf_area, decode_image


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
