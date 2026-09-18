"""
Tests for src/regimes.py's classification rule, persistence filter, and
regime-period builder, per BUILD-SPEC-bitcoin-regime-study.md section 6.4
and section 11's requirement that the persistence filter is tested on a
hand-made label sequence.
"""

import pandas as pd

from src import config, regimes

NASDAQ_THRESHOLD = 0.40
GOLD_THRESHOLD = 0.35
IDIO_THRESHOLD = 0.25


def classify(corr_nasdaq, corr_gold):
    return regimes.classify_regime(corr_nasdaq, corr_gold, NASDAQ_THRESHOLD, GOLD_THRESHOLD, IDIO_THRESHOLD)


def test_classify_regime_risk_asset_at_and_above_threshold():
    assert classify(0.40, 0.10) == config.REGIME_LABEL_RISK_ASSET
    assert classify(0.55, 0.20) == config.REGIME_LABEL_RISK_ASSET


def test_classify_regime_hard_asset_at_and_above_threshold():
    assert classify(0.10, 0.35) == config.REGIME_LABEL_HARD_ASSET
    assert classify(0.05, 0.60) == config.REGIME_LABEL_HARD_ASSET


def test_classify_regime_idiosyncratic_when_both_correlations_small():
    assert classify(0.10, -0.10) == config.REGIME_LABEL_IDIOSYNCRATIC
    assert classify(0.0, 0.0) == config.REGIME_LABEL_IDIOSYNCRATIC


def test_classify_regime_mixed_on_a_tie_at_or_above_both_thresholds():
    # Both correlations clear their own threshold and are exactly equal --
    # neither "and > the other" condition is satisfied, so this is MIXED,
    # not a coin flip toward one asset.
    assert classify(0.50, 0.50) == config.REGIME_LABEL_MIXED


def test_classify_regime_mixed_fallback_below_thresholds_but_not_idiosyncratic():
    # Neither threshold cleared, but corr_nasdaq is not below the
    # idiosyncratic threshold either.
    assert classify(0.30, 0.10) == config.REGIME_LABEL_MIXED


def test_apply_persistence_filter_merges_a_short_interior_run_backward():
    # A 3-day "B" blip inside a long "A" regime, followed by a long "C"
    # regime: the blip should be absorbed into the preceding "A" run, not
    # the following "C" run.
    labels = ["A"] * 20 + ["B"] * 3 + ["C"] * 20
    filtered = regimes.apply_persistence_filter(labels, min_days=15)

    assert filtered == ["A"] * 23 + ["C"] * 20


def test_apply_persistence_filter_short_run_at_the_start_borrows_the_next_labels():
    # A short run at the very start has no preceding run, so it takes on
    # the label of the run that follows it.
    labels = ["A"] * 3 + ["B"] * 20
    filtered = regimes.apply_persistence_filter(labels, min_days=15)

    assert filtered == ["B"] * 23


def test_apply_persistence_filter_cascades_through_back_to_back_short_runs():
    # Two different short runs back to back, both too short to survive on
    # their own, sandwiched between two long runs: both should merge
    # backward into the preceding long run.
    labels = ["A"] * 20 + ["B"] * 5 + ["C"] * 4 + ["D"] * 20
    filtered = regimes.apply_persistence_filter(labels, min_days=15)

    assert filtered == ["A"] * 29 + ["D"] * 20


def test_apply_persistence_filter_leaves_already_long_runs_unchanged():
    labels = ["A"] * 30 + ["B"] * 20 + ["A"] * 25
    filtered = regimes.apply_persistence_filter(labels, min_days=15)

    assert filtered == labels


def test_build_regime_periods_matches_a_known_filtered_sequence():
    dates = pd.date_range("2024-01-01", periods=10, freq="D")
    filtered_labels = ["A"] * 6 + ["B"] * 4

    periods_df = regimes.build_regime_periods(dates, filtered_labels)

    assert list(periods_df["regime_id"]) == [1, 2]
    assert list(periods_df["regime_label"]) == ["A", "B"]
    assert list(periods_df["n_days"]) == [6, 4]
    assert periods_df["start_date"].iloc[0] == "2024-01-01"
    assert periods_df["end_date"].iloc[0] == "2024-01-06"
    assert periods_df["start_date"].iloc[1] == "2024-01-07"
    assert periods_df["end_date"].iloc[1] == "2024-01-10"


def test_build_regimes_daily_assigns_matching_regime_ids():
    dates = pd.date_range("2024-01-01", periods=10, freq="D")
    filtered_labels = ["A"] * 6 + ["B"] * 4

    regimes_daily_df = regimes.build_regimes_daily(dates, filtered_labels)

    assert list(regimes_daily_df["regime_id"].iloc[:6].unique()) == [1]
    assert list(regimes_daily_df["regime_id"].iloc[6:].unique()) == [2]
    assert regimes_daily_df["date"].iloc[0] == "2024-01-01"
    assert regimes_daily_df["date"].iloc[9] == "2024-01-10"
