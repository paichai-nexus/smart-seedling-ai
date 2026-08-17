import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.domain import (  # noqa: E402
    HealthStatus,
    ObservationMetrics,
    classify_status,
    growth_rate_percent,
    stable_seedling_id,
)


class DomainTests(unittest.TestCase):
    def test_fixed_cell_creates_stable_identifier(self):
        self.assertEqual(stable_seedling_id("tray-a", 2, 7), "TRAY-A-R02C07")

    def test_growth_rate_is_relative_change(self):
        self.assertEqual(growth_rate_percent(10, 12.5), 25.0)
        self.assertIsNone(growth_rate_percent(0, 12.5))

    def test_visual_anomaly_requests_expert_review(self):
        metrics = ObservationMetrics(leaf_area_cm2=8, discoloration_ratio=0.25)
        self.assertEqual(classify_status(metrics), HealthStatus.EXPERT_REVIEW)

    def test_shrinking_area_is_warning_not_diagnosis(self):
        previous = ObservationMetrics(leaf_area_cm2=10)
        current = ObservationMetrics(leaf_area_cm2=9)
        self.assertEqual(classify_status(current, previous), HealthStatus.WARNING)


if __name__ == "__main__":
    unittest.main()
