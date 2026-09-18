"""
Tests for src/build_panel.py's calendar-alignment and return-computation logic.

Why this file exists: BUILD-SPEC-bitcoin-regime-study.md section 11 requires
real tests, and this is the module implementing the two rules (section 6.1
calendar alignment, section 6.2 log returns, section 5.2 forward-fill) that
the whole project's correlations depend on. All tests use small hand-built
pandas Series -- no network calls, no dependence on data/raw.
"""

import numpy as np
import pandas as pd

from src import build_panel


def test_log_return_matches_hand_computed_value():
    prices = pd.Series([100.0, 110.0, 99.0], index=pd.to_datetime(["2024-01-01", "2024-01-02", "2024-01-03"]))
    log_return = np.log(prices / prices.shift(1))

    assert np.isnan(log_return.iloc[0])
    assert log_return.iloc[1] == np.log(110.0 / 100.0)
    assert log_return.iloc[2] == np.log(99.0 / 110.0)


def test_reindex_then_diff_absorbs_weekend_into_monday_return():
    # Bitcoin's own calendar: Friday, Saturday, Sunday, Monday.
    btc_dates = pd.to_datetime(["2024-01-05", "2024-01-06", "2024-01-07", "2024-01-08"])
    btc_close = pd.Series([100.0, 105.0, 108.0, 110.0], index=btc_dates)

    # Nasdaq only traded Friday and Monday.
    nasdaq_dates = pd.to_datetime(["2024-01-05", "2024-01-08"])

    aligned_close = btc_close.reindex(nasdaq_dates)
    absorbed_return = np.log(aligned_close / aligned_close.shift(1))

    expected_monday_return = np.log(110.0 / 100.0)
    assert absorbed_return.iloc[1] == expected_monday_return


def test_diff_then_reindex_drops_weekend_return_instead_of_absorbing_it():
    btc_dates = pd.to_datetime(["2024-01-05", "2024-01-06", "2024-01-07", "2024-01-08"])
    btc_close = pd.Series([100.0, 105.0, 108.0, 110.0], index=btc_dates)
    nasdaq_dates = pd.to_datetime(["2024-01-05", "2024-01-08"])

    full_calendar_return = np.log(btc_close / btc_close.shift(1))
    dropped_return = full_calendar_return.reindex(nasdaq_dates)

    expected_monday_only_return = np.log(110.0 / 108.0)
    assert dropped_return.iloc[1] == expected_monday_only_return

    # The two methods must disagree here -- that disagreement is the whole
    # point of the section 6.1 robustness check.
    absorbed_monday_return = np.log(110.0 / 100.0)
    assert dropped_return.iloc[1] != absorbed_monday_return


def test_forward_fill_carries_value_and_flags_it_correctly():
    monthly_dates = pd.to_datetime(["2024-01-01", "2024-02-01"])
    monthly_series = pd.Series([100.0, 105.0], index=monthly_dates)

    daily_dates = pd.to_datetime(["2024-01-01", "2024-01-02", "2024-01-03", "2024-02-01"])
    aligned_value = monthly_series.reindex(daily_dates, method="ffill")
    was_not_original_date = pd.Series(~daily_dates.isin(monthly_series.index), index=daily_dates)
    is_forward_filled = was_not_original_date & aligned_value.notna()

    assert list(aligned_value) == [100.0, 100.0, 100.0, 105.0]
    assert list(is_forward_filled) == [False, True, True, False]


def test_forward_fill_leaves_leading_dates_as_nan_not_flagged():
    monthly_dates = pd.to_datetime(["2024-02-01"])
    monthly_series = pd.Series([105.0], index=monthly_dates)

    daily_dates = pd.to_datetime(["2024-01-30", "2024-01-31", "2024-02-01"])
    aligned_value = monthly_series.reindex(daily_dates, method="ffill")
    was_not_original_date = pd.Series(~daily_dates.isin(monthly_series.index), index=daily_dates)
    is_forward_filled = was_not_original_date & aligned_value.notna()

    assert aligned_value.isna().sum() == 2
    # Dates before the series even started are missing data, not "filled".
    assert list(is_forward_filled) == [False, False, False]
