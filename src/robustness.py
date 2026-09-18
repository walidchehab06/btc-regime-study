"""
Robustness tables for the correlation results, per
BUILD-SPEC-bitcoin-regime-study.md sections 6.1 and 6.3 (Phase 9).

Why this file exists: section 6.1 asks whether the headline correlations
change when weekend returns are dropped instead of absorbed, section 6.3
asks where Pearson and Spearman disagree, and figure 2 shows how much the
window length matters. Phases 2 and 4 built the inputs for all three, but
none of them wrote the answer to a table. This file does, so every
robustness number quoted in docs/ has a CSV behind it. It uses no new
data: it reads the two panels and the rolling_correlations table that
earlier phases already built.
"""

import sqlite3
import sys

import pandas as pd

from src import config, correlations


def load_rolling_correlations_wide(conn):
    """
    Load the stored rolling correlations and pivot them to one column per
    pair/window/method.

    Why it exists: the Pearson-vs-Spearman and window comparisons both need
    several series for the same date side by side.

    Parameters:
        conn: open sqlite3 connection to btc_regime.db.

    Returns:
        pandas.DataFrame indexed by date (datetime), one column per
        (pair, window, method) tuple.
    """
    long_table = pd.read_sql_query(
        "SELECT date, pair, window, method, correlation FROM rolling_correlations", conn
    )
    print(f"[robustness] loaded {len(long_table)} rows from rolling_correlations")
    long_table["date"] = pd.to_datetime(long_table["date"])
    wide_table = long_table.pivot_table(
        index="date", columns=["pair", "window", "method"], values="correlation"
    )
    return wide_table


def build_weekend_handling_table(panel_primary, panel_alt_weekend):
    """
    Compare the 90-day BTC correlations under the two weekend-handling rules.

    Why it exists: BUILD-SPEC section 6.1 requires reporting whether the
    headline correlations change materially when Bitcoin's weekend returns
    are dropped instead of absorbed into Monday's return.

    Parameters:
        panel_primary: pandas.DataFrame, panel_daily.parquet (weekend
            returns absorbed into Monday).
        panel_alt_weekend: pandas.DataFrame, panel_daily_alt_weekend.parquet
            (weekend returns dropped). Same index as panel_primary.

    Returns:
        pandas.DataFrame, one row per pair in config.CORRELATION_PAIRS.
    """
    assert panel_primary.index.equals(panel_alt_weekend.index), "the two panels must share a date index"

    window = config.CORRELATION_WINDOW_HEADLINE
    rows = []
    for pair_label, (column_a, column_b) in config.CORRELATION_PAIRS.items():
        rolling_primary = correlations.rolling_pearson_pandas(panel_primary[column_a], panel_primary[column_b], window)
        rolling_alt = correlations.rolling_pearson_pandas(panel_alt_weekend[column_a], panel_alt_weekend[column_b], window)

        both_present = rolling_primary.notna() & rolling_alt.notna()
        absolute_difference = (rolling_primary - rolling_alt).abs()[both_present]
        latest_date = both_present[both_present].index.max()

        full_period_primary = panel_primary[column_a].corr(panel_primary[column_b])
        full_period_alt = panel_alt_weekend[column_a].corr(panel_alt_weekend[column_b])

        rows.append(
            {
                "pair": pair_label,
                "n_days_compared": int(both_present.sum()),
                "latest_date": latest_date.strftime("%Y-%m-%d"),
                "latest_90d_absorbed": rolling_primary.loc[latest_date],
                "latest_90d_dropped": rolling_alt.loc[latest_date],
                "latest_delta": rolling_alt.loc[latest_date] - rolling_primary.loc[latest_date],
                "mean_abs_delta_90d": absolute_difference.mean(),
                "max_abs_delta_90d": absolute_difference.max(),
                "full_period_absorbed": full_period_primary,
                "full_period_dropped": full_period_alt,
                "full_period_delta": full_period_alt - full_period_primary,
            }
        )

    table = pd.DataFrame(rows)
    print(f"[robustness] weekend-handling table: {len(table)} rows")
    return table


def build_pearson_vs_spearman_table(rolling_wide):
    """
    Summarise where the 90-day Pearson and Spearman correlations disagree.

    Why it exists: BUILD-SPEC section 6.3 requires reporting where the two
    methods disagree notably, since Pearson is sensitive to outlier days.

    Parameters:
        rolling_wide: pandas.DataFrame from load_rolling_correlations_wide().

    Returns:
        pandas.DataFrame, one row per pair in config.CORRELATION_PAIRS.
    """
    window = config.CORRELATION_WINDOW_HEADLINE
    rows = []
    for pair_label in config.CORRELATION_PAIRS:
        pearson = rolling_wide[(pair_label, window, "pearson")]
        spearman = rolling_wide[(pair_label, window, "spearman")]

        both_present = pearson.notna() & spearman.notna()
        absolute_difference = (pearson - spearman).abs()[both_present]
        n_notable = int((absolute_difference > config.ROBUSTNESS_NOTABLE_DIFFERENCE).sum())
        latest_date = both_present[both_present].index.max()

        rows.append(
            {
                "pair": pair_label,
                "n_days_compared": int(both_present.sum()),
                "mean_abs_difference": absolute_difference.mean(),
                "max_abs_difference": absolute_difference.max(),
                "date_of_max_difference": absolute_difference.idxmax().strftime("%Y-%m-%d"),
                "notable_difference_threshold": config.ROBUSTNESS_NOTABLE_DIFFERENCE,
                "n_days_notable": n_notable,
                "share_days_notable": n_notable / int(both_present.sum()),
                "latest_date": latest_date.strftime("%Y-%m-%d"),
                "latest_pearson_90d": pearson.loc[latest_date],
                "latest_spearman_90d": spearman.loc[latest_date],
            }
        )

    table = pd.DataFrame(rows)
    print(f"[robustness] pearson-vs-spearman table: {len(table)} rows")
    return table


def build_window_comparison_table(rolling_wide):
    """
    Summarise how much the 30-day and 90-day Pearson correlations differ.

    Why it exists: figure 2 shows the window-length effect visually; this
    table puts numbers behind it. Compared only on dates where both windows
    exist, so the 30-day series is not credited with its extra early history.

    Parameters:
        rolling_wide: pandas.DataFrame from load_rolling_correlations_wide().

    Returns:
        pandas.DataFrame, one row per pair in config.CORRELATION_PAIRS.
    """
    rows = []
    for pair_label in config.CORRELATION_PAIRS:
        short_window = rolling_wide[(pair_label, config.CORRELATION_WINDOW_SHORT, "pearson")]
        headline_window = rolling_wide[(pair_label, config.CORRELATION_WINDOW_HEADLINE, "pearson")]

        both_present = short_window.notna() & headline_window.notna()
        short_common = short_window[both_present]
        headline_common = headline_window[both_present]
        signs_differ = (short_common > 0) != (headline_common > 0)

        rows.append(
            {
                "pair": pair_label,
                "n_days_compared": int(both_present.sum()),
                "std_30d": short_common.std(),
                "std_90d": headline_common.std(),
                "min_30d": short_common.min(),
                "max_30d": short_common.max(),
                "min_90d": headline_common.min(),
                "max_90d": headline_common.max(),
                "mean_abs_difference": (short_common - headline_common).abs().mean(),
                "share_days_sign_differs": signs_differ.mean(),
            }
        )

    table = pd.DataFrame(rows)
    print(f"[robustness] window-comparison table: {len(table)} rows")
    return table


def build_latest_snapshot_table(rolling_wide):
    """
    Report the most recent 30-day and 90-day correlation readings per pair.

    Why it exists: the write-up quotes where the correlations stand at the
    end of the sample, and the figures show that only graphically.

    Parameters:
        rolling_wide: pandas.DataFrame from load_rolling_correlations_wide().

    Returns:
        pandas.DataFrame, one row per pair in config.CORRELATION_PAIRS.
    """
    rows = []
    for pair_label in config.CORRELATION_PAIRS:
        pearson_90d = rolling_wide[(pair_label, config.CORRELATION_WINDOW_HEADLINE, "pearson")].dropna()
        latest_date = pearson_90d.index.max()
        rows.append(
            {
                "pair": pair_label,
                "date": latest_date.strftime("%Y-%m-%d"),
                "pearson_30d": rolling_wide[(pair_label, config.CORRELATION_WINDOW_SHORT, "pearson")].loc[latest_date],
                "pearson_90d": pearson_90d.loc[latest_date],
                "spearman_90d": rolling_wide[(pair_label, config.CORRELATION_WINDOW_HEADLINE, "spearman")].loc[latest_date],
            }
        )

    table = pd.DataFrame(rows)
    print(f"[robustness] latest-snapshot table: {len(table)} rows")
    return table


def main():
    """
    Build and write the four robustness tables.

    Why it exists: this is the entry point src/run_all.py calls for the
    Phase 9 robustness step. It runs after Phase 4 has loaded
    rolling_correlations.

    Parameters:
        None.

    Returns:
        None.
    """
    panel_primary = pd.read_parquet(config.PANEL_PATH)
    panel_alt_weekend = pd.read_parquet(config.PANEL_ALT_WEEKEND_PATH)
    print(
        f"[robustness] loaded panels: primary {len(panel_primary)} rows, "
        f"alt-weekend {len(panel_alt_weekend)} rows"
    )

    conn = sqlite3.connect(config.DB_PATH)
    try:
        rolling_wide = load_rolling_correlations_wide(conn)
    finally:
        conn.close()

    tables_to_write = [
        (build_weekend_handling_table(panel_primary, panel_alt_weekend), config.ROBUSTNESS_WEEKEND_TABLE_PATH),
        (build_pearson_vs_spearman_table(rolling_wide), config.ROBUSTNESS_PEARSON_VS_SPEARMAN_TABLE_PATH),
        (build_window_comparison_table(rolling_wide), config.ROBUSTNESS_WINDOW_TABLE_PATH),
        (build_latest_snapshot_table(rolling_wide), config.CORRELATION_LATEST_SNAPSHOT_TABLE_PATH),
    ]
    for table, path in tables_to_write:
        table.to_csv(path, index=False)
        print(f"[robustness] wrote {path} ({len(table)} rows)")


if __name__ == "__main__":
    main()
    sys.exit(0)
