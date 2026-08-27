from __future__ import annotations

from dataclasses import dataclass
from statistics import fmean, median, pstdev
from typing import Iterable, Mapping


@dataclass(frozen=True)
class GrowthSample:
    seedling_id: str
    initial_leaf_area_cm2: float
    final_leaf_area_cm2: float
    growth_rate_percent: float
    observation_count: int


@dataclass(frozen=True)
class GroupGrowthSummary:
    group_id: int
    group_name: str
    group_kind: str
    sample_size: int
    mean_growth_rate_percent: float
    median_growth_rate_percent: float
    standard_deviation_percent: float
    minimum_growth_rate_percent: float
    maximum_growth_rate_percent: float
    samples: tuple[GrowthSample, ...]


def summarize_group_growth(
    group_id: int,
    group_name: str,
    group_kind: str,
    observation_rows: Iterable[Mapping],
) -> GroupGrowthSummary:
    """Summarize relative leaf-area change for seedlings with 2+ observations."""
    by_seedling = {}
    for row in observation_rows:
        by_seedling.setdefault(str(row["seedling_id"]), []).append(row)

    samples = []
    for seedling_id, rows in sorted(by_seedling.items()):
        ordered = sorted(rows, key=lambda row: str(row["captured_at"]))
        initial = float(ordered[0]["leaf_area_cm2"])
        final = float(ordered[-1]["leaf_area_cm2"])
        if len(ordered) < 2 or initial <= 0:
            continue
        growth = ((final - initial) / initial) * 100
        samples.append(
            GrowthSample(
                seedling_id=seedling_id,
                initial_leaf_area_cm2=round(initial, 3),
                final_leaf_area_cm2=round(final, 3),
                growth_rate_percent=round(growth, 2),
                observation_count=len(ordered),
            )
        )

    rates = [sample.growth_rate_percent for sample in samples]
    if not rates:
        return GroupGrowthSummary(
            group_id=group_id,
            group_name=group_name,
            group_kind=group_kind,
            sample_size=0,
            mean_growth_rate_percent=0,
            median_growth_rate_percent=0,
            standard_deviation_percent=0,
            minimum_growth_rate_percent=0,
            maximum_growth_rate_percent=0,
            samples=(),
        )
    return GroupGrowthSummary(
        group_id=group_id,
        group_name=group_name,
        group_kind=group_kind,
        sample_size=len(rates),
        mean_growth_rate_percent=round(fmean(rates), 2),
        median_growth_rate_percent=round(median(rates), 2),
        standard_deviation_percent=round(pstdev(rates), 2),
        minimum_growth_rate_percent=round(min(rates), 2),
        maximum_growth_rate_percent=round(max(rates), 2),
        samples=tuple(samples),
    )
