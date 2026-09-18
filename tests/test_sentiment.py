"""
Tests for src/sentiment.py's sentiment bucketing, forward-return window,
and transition-proximity calculation, per
BUILD-SPEC-bitcoin-regime-study.md section 6.6 and section 11's
requirement that hand-written calculations are tested against known
cases.
"""

import numpy as np
import pandas as pd

from src import sentiment


def test_assign_sentiment_bucket_boundaries():
    fng_value = pd.Series([5.0, 20.0, 21.0, 50.0, 79.0, 80.0, 95.0, np.nan])
    bucket = sentiment.assign_sentiment_bucket(fng_value)

    assert list(bucket) == [
        "EXTREME_FEAR",
        "EXTREME_FEAR",
        "MODERATE",
        "MODERATE",
        "MODERATE",
        "EXTREME_GREED",
        "EXTREME_GREED",
        None,
    ]


def test_compute_forward_log_returns_sums_the_next_n_days_only():
    # Day-by-day log returns 0.1, 0.2, 0.3, 0.4, 0.5. The forward 2-day
    # return at day 0 is days 1+2 (0.2 + 0.3 = 0.5), not day 0 itself.
    dates = pd.date_range("2024-01-01", periods=5, freq="D")
    log_returns = pd.Series([0.1, 0.2, 0.3, 0.4, 0.5], index=dates)

    forward_2d = sentiment.compute_forward_log_returns(log_returns, horizon_days=2)

    assert np.isclose(forward_2d.iloc[0], 0.5)
    assert np.isclose(forward_2d.iloc[1], 0.7)
    assert np.isclose(forward_2d.iloc[2], 0.9)
    # The last two days don't have a full 2-day-ahead window.
    assert pd.isna(forward_2d.iloc[3])
    assert pd.isna(forward_2d.iloc[4])


def test_compute_days_to_nearest_transition_zero_at_period_edges():
    # A single 5-day regime period: day 0 and day 4 are both boundaries
    # (distance 0), day 2 is the furthest interior point (distance 2).
    regimes_daily_df = pd.DataFrame(
        {
            "date": [f"2024-01-0{d}" for d in range(1, 6)],
            "regime_id": [1, 1, 1, 1, 1],
        }
    )

    result = sentiment.compute_days_to_nearest_transition(regimes_daily_df)

    assert list(result["days_to_nearest_transition"]) == [0, 1, 2, 1, 0]


def test_compute_days_to_nearest_transition_across_two_periods():
    # Two adjacent 3-day periods: the boundary day of each period (first
    # and last day) is distance 0, independent of the other period.
    regimes_daily_df = pd.DataFrame(
        {
            "date": [f"2024-01-0{d}" for d in range(1, 7)],
            "regime_id": [1, 1, 1, 2, 2, 2],
        }
    )

    result = sentiment.compute_days_to_nearest_transition(regimes_daily_df)

    assert list(result["days_to_nearest_transition"]) == [0, 1, 0, 0, 1, 0]
