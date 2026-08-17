from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Optional


@dataclass(frozen=True)
class RuleCandidate:
    rule_id: int
    matched_signals: tuple[str, ...]
    match_score: float


def derive_observable_signals(
    discoloration_ratio: float,
    damage_ratio: float,
    confidence: float,
    growth_rate_percent: Optional[float],
) -> set[str]:
    """Translate measurements into auditable, non-diagnostic signals."""
    signals = set()
    if discoloration_ratio >= 0.08:
        signals.add("discoloration")
    if damage_ratio >= 0.05:
        signals.add("damage")
    if confidence < 0.6:
        signals.add("low_confidence")
    if growth_rate_percent is not None:
        if growth_rate_percent < 0:
            signals.add("growth_decline")
        elif growth_rate_percent < 5:
            signals.add("growth_slowdown")
    return signals


def rank_knowledge_rules(
    observed_signals: set[str],
    rules: Iterable[tuple[int, Iterable[str]]],
) -> list[RuleCandidate]:
    """Rank approved rules by signal coverage without inferring a diagnosis."""
    candidates = []
    for rule_id, rule_signals in rules:
        normalized = {signal.strip().lower() for signal in rule_signals if signal.strip()}
        matched = tuple(sorted(observed_signals & normalized))
        if not matched:
            continue
        score = len(matched) / len(normalized)
        candidates.append(
            RuleCandidate(
                rule_id=rule_id,
                matched_signals=matched,
                match_score=round(score, 3),
            )
        )
    return sorted(candidates, key=lambda item: (-item.match_score, item.rule_id))
