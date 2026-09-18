"""
Tests for src/correlations.py, per BUILD-SPEC-bitcoin-regime-study.md
section 6.3 and section 12 (Phase 4). All tests use small synthetic series
-- no dependence on data/raw or data/processed.
"""

import re

import numpy as np
import pandas as pd

from src import config, correlations


def test_rolling_pearson_pandas_matches_hand_written_within_tolerance():
    rng = np.random.default_rng(seed=1)
    dates = pd.date_range("2024-01-01", periods=200, freq="D")
    series_a = pd.Series(rng.normal(size=200), index=dates)
    series_b = pd.Series(0.5 * series_a.values + rng.normal(size=200) * 0.6, index=dates)

    from src import core_math

    pandas_version = correlations.rolling_pearson_pandas(series_a, series_b, window=config.CORRELATION_WINDOW_HEADLINE)
    hand_written_version = core_math.rolling_pearson_hand_written(
        series_a, series_b, window=config.CORRELATION_WINDOW_HEADLINE
    )

    correlations.assert_pandas_and_hand_written_agree(
        pandas_version, hand_written_version, config.CORRELATION_TOLERANCE
    )


def test_assert_pandas_and_hand_written_agree_raises_on_planted_mismatch():
    dates = pd.date_range("2024-01-01", periods=5, freq="D")
    pandas_version = pd.Series([0.1, 0.2, 0.3, np.nan, 0.5], index=dates)
    hand_written_version = pandas_version.copy()
    hand_written_version.iloc[2] = 0.9  # planted mismatch, well above tolerance

    try:
        correlations.assert_pandas_and_hand_written_agree(pandas_version, hand_written_version, tolerance=1e-9)
        assert False, "expected an AssertionError for the planted mismatch"
    except AssertionError as error:
        assert "disagree" in str(error)


def test_rolling_spearman_is_one_for_a_strictly_monotonic_nonlinear_pair():
    # y = x**3 is strictly increasing but not linear in x, so Pearson
    # correlation over the window is close to but not exactly 1.0, while
    # Spearman -- which only sees rank order -- must be exactly 1.0. This
    # is the property that makes Spearman a genuinely different robustness
    # check, not a restatement of Pearson.
    dates = pd.date_range("2024-01-01", periods=40, freq="D")
    x_values = np.linspace(-3, 3, 40)
    series_a = pd.Series(x_values, index=dates)
    series_b = pd.Series(x_values**3, index=dates)

    spearman = correlations.rolling_spearman(series_a, series_b, window=20)
    pearson = correlations.rolling_pearson_pandas(series_a, series_b, window=20)

    non_nan_spearman = spearman.dropna()
    assert len(non_nan_spearman) > 0
    assert np.allclose(non_nan_spearman.values, 1.0, atol=1e-9)

    non_nan_pearson = pearson.dropna()
    assert not np.allclose(non_nan_pearson.values, 1.0, atol=1e-9)


def test_rolling_spearman_has_no_partial_windows():
    dates = pd.date_range("2024-01-01", periods=10, freq="D")
    series_a = pd.Series(range(10), index=dates, dtype=float)
    series_b = pd.Series(range(10), index=dates, dtype=float)

    result = correlations.rolling_spearman(series_a, series_b, window=5)

    assert result.iloc[:4].isna().all()
    assert result.iloc[4:].notna().all()


def _make_small_panel():
    dates = pd.date_range("2024-01-01", periods=150, freq="D")
    rng = np.random.default_rng(seed=3)
    btc = rng.normal(size=150)
    panel = pd.DataFrame(
        {
            "log_return_BTC-USD": btc,
            "log_return_^IXIC": 0.3 * btc + rng.normal(size=150) * 0.8,
            "log_return_GLD": 0.1 * btc + rng.normal(size=150) * 0.9,
            "log_return_DX-Y.NYB": -0.2 * btc + rng.normal(size=150) * 0.9,
        },
        index=dates,
    )
    panel.index.name = "date"
    return panel


def test_build_all_rolling_correlations_matches_rolling_correlations_schema():
    panel = _make_small_panel()

    correlations_df, hand_written_check_df = correlations.build_all_rolling_correlations(panel)

    assert list(correlations_df.columns) == ["date", "pair", "window", "method", "correlation"]
    assert set(correlations_df["pair"].unique()) == set(config.CORRELATION_PAIRS)
    assert set(correlations_df["window"].unique()) <= {config.CORRELATION_WINDOW_SHORT, config.CORRELATION_WINDOW_HEADLINE}
    assert set(correlations_df["method"].unique()) == {"pearson", "spearman"}
    assert correlations_df["correlation"].between(-1.0, 1.0).all()
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}", correlations_df["date"].iloc[0])

    assert list(hand_written_check_df.columns) == ["date", "pair", "window", "method", "correlation"]
    assert (hand_written_check_df["window"] == config.CORRELATION_WINDOW_HEADLINE).all()
    assert (hand_written_check_df["method"] == "pearson").all()
