"""
Tests for src/core_math.py's hand-written Pearson correlation, per
BUILD-SPEC-bitcoin-regime-study.md section 6.3 and section 11's requirement
that the hand-written correlation is tested against known cases and against
pandas.
"""

import math

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


def test_annualized_return_of_a_constant_daily_log_return():
    daily_log_return = 0.01
    log_returns = np.full(252, daily_log_return)

    result = core_math.annualized_return(log_returns, trading_days_per_year=252)
    expected = math.exp(daily_log_return * 252) - 1

    assert np.isclose(result, expected)


def test_annualized_return_of_zero_returns_is_zero():
    log_returns = np.zeros(50)

    assert np.isclose(core_math.annualized_return(log_returns, trading_days_per_year=252), 0.0)


def test_annualized_volatility_of_an_alternating_series():
    # Alternating +/-0.02 has zero mean and a population standard
    # deviation of exactly 0.02, computable by hand.
    log_returns = np.array([0.02, -0.02, 0.02, -0.02])

    result = core_math.annualized_volatility(log_returns, trading_days_per_year=252)
    expected = 0.02 * math.sqrt(252)

    assert np.isclose(result, expected)


def test_max_drawdown_of_a_known_price_path():
    # Peak of 120 at position 1, trough of 80 at position 4: (80-120)/120.
    prices = np.array([100.0, 120.0, 90.0, 110.0, 80.0, 130.0])

    result = core_math.max_drawdown(prices)
    expected = (80.0 - 120.0) / 120.0

    assert np.isclose(result, expected)


def test_max_drawdown_of_a_strictly_increasing_series_is_zero():
    prices = np.array([100.0, 110.0, 120.0, 130.0])

    assert np.isclose(core_math.max_drawdown(prices), 0.0)
