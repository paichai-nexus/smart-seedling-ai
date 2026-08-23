import unittest

import numpy as np

from app.evaluation.hsv_metrics import evaluate_binary_masks


class TestSegmentationMetrics(unittest.TestCase):

    def test_perfect_match(self):
        mask = np.array([
            [0, 1],
            [1, 0],
        ], dtype=np.uint8)

        result = evaluate_binary_masks(mask, mask)

        self.assertEqual(result.intersection, 2)
        self.assertEqual(result.union, 2)
        self.assertEqual(result.iou, 1.0)
        self.assertEqual(result.dice, 1.0)
        self.assertEqual(result.area_absolute_error, 0)
        self.assertEqual(result.area_percentage_error, 0.0)

    def test_partial_overlap(self):
        predicted = np.array([
            [1, 1],
            [0, 0],
        ], dtype=np.uint8)

        ground_truth = np.array([
            [1, 0],
            [1, 0],
        ], dtype=np.uint8)

        result = evaluate_binary_masks(predicted, ground_truth)

        self.assertEqual(result.intersection, 1)
        self.assertEqual(result.union, 3)
        self.assertAlmostEqual(result.iou, 1 / 3)
        self.assertAlmostEqual(result.dice, 0.5)

    def test_shape_mismatch(self):
        predicted = np.zeros((2, 2), dtype=np.uint8)
        ground_truth = np.zeros((3, 3), dtype=np.uint8)

        with self.assertRaises(ValueError):
            evaluate_binary_masks(predicted, ground_truth)


if __name__ == "__main__":
    unittest.main()
