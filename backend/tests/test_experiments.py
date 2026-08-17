from app.experiments import summarize_group_growth


def test_group_growth_uses_first_and_last_observation_per_seedling():
    rows = [
        {"seedling_id": "S-1", "captured_at": "2026-08-01", "leaf_area_cm2": 10},
        {"seedling_id": "S-1", "captured_at": "2026-08-03", "leaf_area_cm2": 12},
        {"seedling_id": "S-1", "captured_at": "2026-08-05", "leaf_area_cm2": 15},
        {"seedling_id": "S-2", "captured_at": "2026-08-01", "leaf_area_cm2": 20},
        {"seedling_id": "S-2", "captured_at": "2026-08-05", "leaf_area_cm2": 22},
    ]
    summary = summarize_group_growth(1, "control", "control", rows)
    assert summary.sample_size == 2
    assert summary.mean_growth_rate_percent == 30
    assert summary.median_growth_rate_percent == 30
    assert summary.standard_deviation_percent == 20
    assert [sample.growth_rate_percent for sample in summary.samples] == [50, 10]


def test_seedling_without_two_valid_observations_is_excluded():
    rows = [
        {"seedling_id": "S-1", "captured_at": "2026-08-01", "leaf_area_cm2": 10},
        {"seedling_id": "S-2", "captured_at": "2026-08-01", "leaf_area_cm2": 0},
        {"seedling_id": "S-2", "captured_at": "2026-08-02", "leaf_area_cm2": 5},
    ]
    summary = summarize_group_growth(2, "treatment", "treatment", rows)
    assert summary.sample_size == 0
    assert summary.samples == ()
