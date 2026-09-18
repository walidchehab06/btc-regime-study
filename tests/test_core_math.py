"""
Tests for src/core_math.py's hand-written Pearson correlation, per
BUILD-SPEC-bitcoin-regime-study.md section 6.3 and section 11's requirement
that the hand-written correlation is tested against known cases and against
pandas.
"""

import numpy as np
import pandas as pd

from src import core_math


def test_pearson_correlation_of_identical_series_is_one():
    x = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
    y = np.array([1.0, 2.0, 3.0, 4.0, 5.0])

    assert np.isclose(core_math.pearson_correlation(x, y), 1.0)


def test_pearson_correlation_of_inverted_series_is_negative_one():
    x = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
    y = np.array([5.0, 4.0, 3.0, 2.0, 1.0])

    assert np.isclose(core_math.pearson_correlation(x, y), -1.0)


def test_pearson_correlation_of_symmetric_unrelated_series_is_zero():
    # A hand-picked pair whose covariance sums to exactly zero: x is a
    # straight ramp, y is symmetric around its own mean in a way that
    # cancels x's deviations above and below its mean.
    x = np.array([1.0, 2.0, 3.0, 4.0])
    y = np.array([1.0, -1.0, -1.0, 1.0])

    assert np.isclose(core_math.pearson_correlation(x, y), 0.0, atol=1e-10)


def test_pearson_correlation_matches_numpy_corrcoef_on_random_data():
    rng = np.random.default_rng(seed=42)
    x = rng.normal(size=500)
    y = 0.6 * x + rng.normal(size=500) * 0.5

    hand_written = core_math.pearson_correlation(x, y)
    reference = np.corrcoef(x, y)[0, 1]

    assert np.isclose(hand_written, reference, atol=1e-10)


def test_rolling_pearson_hand_written_matches_pandas_rolling_corr():
    rng = np.random.default_rng(seed=7)
    dates = pd.date_range("2024-01-01", periods=200, freq="D")
    series_a = pd.Series(rng.normal(size=200), index=dates)
    series_b = pd.Series(0.4 * series_a.values + rng.normal(size=200) * 0.7, index=dates)

    hand_written = core_math.rolling_pearson_hand_written(series_a, series_b, window=30)
    pandas_version = series_a.rolling(30, min_periods=30).corr(series_b)

    both_present = hand_written.notna() & pandas_version.notna()
    assert both_present.sum() > 0
    assert np.allclose(hand_written[both_present], pandas_version[both_present], atol=1e-9)


def test_rolling_pearson_hand_written_has_no_partial_windows():
    dates = pd.date_range("2024-01-01", periods=10, freq="D")
    series_a = pd.Series(range(10), index=dates, dtype=float)
    series_b = pd.Series(range(10), index=dates, dtype=float)

    result = core_math.rolling_pearson_hand_written(series_a, series_b, window=5)

    assert result.iloc[:4].isna().all()
    assert result.iloc[4:].notna().all()
