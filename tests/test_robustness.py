"""
Tests for src/robustness.py's summary tables, per
BUILD-SPEC-bitcoin-regime-study.md sections 6.1 and 6.3.

The inputs here are small hand-built frames with known answers, not real
market data, so a wrong formula shows up as a wrong number.
"""

import numpy as np
import pandas as pd

from src import config, robustness


def make_panel(n_days=150, seed=7):
    """Build a panel with the return columns the three pairs read."""
    random_generator = np.random.default_rng(seed)
    dates = pd.date_range("2024-01-01", periods=n_days, freq="B")
    columns = {
        "log_return_BTC-USD": random_generator.normal(size=n_days),
        "log_return_^IXIC": random_generator.normal(size=n_days),
        "log_return_GLD": random_generator.normal(size=n_days),
        "log_return_DX-Y.NYB": random_generator.normal(size=n_days),
    }
    return pd.DataFrame(columns, index=dates)


def make_rolling_wide(pearson_90d, spearman_90d, pearson_30d):
    """Build the (pair, window, method) column layout with constant values."""
    dates = pd.date_range("2024-01-01", periods=10, freq="B")
    columns = {}
    for pair_label in config.CORRELATION_PAIRS:
        columns[(pair_label, config.CORRELATION_WINDOW_HEADLINE, "pearson")] = pearson_90d
        columns[(pair_label, config.CORRELATION_WINDOW_HEADLINE, "spearman")] = spearman_90d
        columns[(pair_label, config.CORRELATION_WINDOW_SHORT, "pearson")] = pearson_30d
    wide = pd.DataFrame(columns, index=dates)
    wide.columns = pd.MultiIndex.from_tuples(wide.columns, names=["pair", "window", "method"])
    return wide


def test_weekend_table_is_zero_when_the_two_panels_are_identical():
    panel = make_panel()

    table = robustness.build_weekend_handling_table(panel, panel.copy())

    assert len(table) == len(config.CORRELATION_PAIRS)
    assert np.allclose(table["max_abs_delta_90d"], 0.0)
    assert np.allclose(table["full_period_delta"], 0.0)


def test_weekend_table_reports_a_change_when_bitcoin_returns_differ():
    panel = make_panel()
    altered_panel = panel.copy()
    altered_panel["log_return_BTC-USD"] = np.random.default_rng(99).normal(size=len(panel))

    table = robustness.build_weekend_handling_table(panel, altered_panel)

    assert (table["max_abs_delta_90d"] > 0.0).all()


def test_pearson_vs_spearman_table_counts_notable_days():
    # A constant 0.2 gap is above the 0.10 reporting threshold on every day.
    wide = make_rolling_wide(pearson_90d=0.5, spearman_90d=0.3, pearson_30d=0.5)

    table = robustness.build_pearson_vs_spearman_table(wide)

    assert np.allclose(table["mean_abs_difference"], 0.2)
    assert (table["n_days_notable"] == 10).all()
    assert np.allclose(table["share_days_notable"], 1.0)


def test_window_table_flags_days_where_the_sign_differs():
    # 30-day reading is negative and 90-day reading is positive on every day.
    wide = make_rolling_wide(pearson_90d=0.4, spearman_90d=0.4, pearson_30d=-0.1)

    table = robustness.build_window_comparison_table(wide)

    assert np.allclose(table["share_days_sign_differs"], 1.0)
    assert np.allclose(table["mean_abs_difference"], 0.5)


def test_latest_snapshot_uses_the_last_date_with_a_90_day_reading():
    wide = make_rolling_wide(pearson_90d=0.4, spearman_90d=0.35, pearson_30d=0.6)

    table = robustness.build_latest_snapshot_table(wide)

    assert (table["date"] == wide.index.max().strftime("%Y-%m-%d")).all()
    assert np.allclose(table["pearson_90d"], 0.4)
    assert np.allclose(table["spearman_90d"], 0.35)
