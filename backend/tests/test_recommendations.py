from app.recommendations import derive_observable_signals, rank_knowledge_rules


def test_measurements_become_non_diagnostic_observable_signals():
    signals = derive_observable_signals(
        discoloration_ratio=0.12,
        damage_ratio=0.07,
        confidence=0.9,
        growth_rate_percent=-3,
    )
    assert signals == {"discoloration", "damage", "growth_decline"}


def test_rules_are_ranked_by_observed_signal_coverage():
    candidates = rank_knowledge_rules(
        {"discoloration", "growth_slowdown"},
        [
            (1, ["discoloration", "growth_slowdown"]),
            (2, ["discoloration", "damage", "growth_slowdown"]),
            (3, ["damage"]),
        ],
    )
    assert [candidate.rule_id for candidate in candidates] == [1, 2]
    assert candidates[0].match_score == 1.0
    assert candidates[1].match_score == 0.667


def test_rule_with_no_evidence_is_not_returned():
    assert rank_knowledge_rules({"discoloration"}, [(1, ["damage"])]) == []
