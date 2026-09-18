"""
Rolling correlations between Bitcoin and Nasdaq, gold, and the dollar
index, per BUILD-SPEC-bitcoin-regime-study.md section 12 (Phase 4).

Why this file exists: this is where section 6.3's rolling-correlation
methodology is actually computed -- the pandas implementation, the
hand-written NumPy implementation (src/core_math.py) for the headline
90-day Pearson window, and the Spearman robustness check -- and where the
long-format table sql/schema.sql's rolling_correlations expects gets
assembled and loaded.
"""

import sys

import pandas as pd
import sqlite3

from src import config, core_math, database


def load_panel():
    """
    Load the primary daily panel built in Phase 2.

    Why it exists: correlations are computed from the same source as every
    other Phase 3/4 table, panel_daily.parquet.

    Parameters:
        None.

    Returns:
        pandas.DataFrame indexed by date (datetime), as saved by
        src/build_panel.py.
    """
    panel = pd.read_parquet(config.PANEL_PATH)
    print(f"[correlations] loaded {config.PANEL_PATH}: {len(panel)} rows, {len(panel.columns)} columns")
    return panel


def rolling_pearson_pandas(series_a, series_b, window):
    """
    Compute a rolling Pearson correlation using pandas' own .rolling().corr().

    Why it exists: this is the first of the two independent
    implementations BUILD-SPEC section 6.3 requires for the 90-day
    window -- the ordinary, library-provided way of doing it, checked
    against src/core_math.py's hand-written version.

    Parameters:
        series_a: pandas.Series, aligned to the same date index as series_b.
        series_b: pandas.Series, aligned to the same date index as series_a.
        window: int, number of trading days in the rolling window.

    Returns:
        pandas.Series of correlations, indexed like series_a, NaN before
        the first full window (min_periods=window, no partial windows,
        per section 6.3).
    """
    return series_a.rolling(window, min_periods=window).corr(series_b)


def rolling_spearman(series_a, series_b, window):
    """
    Compute a rolling Spearman rank correlation.

    Why it exists: BUILD-SPEC section 6.3 requires Spearman as a
    robustness check on the 90-day window, since Pearson is sensitive to
    outliers and crypto returns have extreme days. Spearman correlation is
    defined as the Pearson correlation of the *ranks* of the data, so this
    reuses core_math.pearson_correlation() on within-window ranks instead
    of adding a scipy dependency for scipy.stats.spearmanr -- see
    docs/decisions-log.md. The ranks must be computed separately for each
    window (a value's rank depends on what else is in that window), not
    once over the whole series, which is why this cannot be written as
    "rank the whole series, then call rolling_pearson_pandas on the ranks".

    Parameters:
        series_a: pandas.Series, aligned to the same date index as series_b.
        series_b: pandas.Series, aligned to the same date index as series_a.
        window: int, number of trading days in the rolling window.

    Returns:
        pandas.Series of Spearman correlations, indexed like series_a,
        NaN before the first full window and at any window containing a
        NaN in either input series.
    """
    assert series_a.index.equals(series_b.index), "series_a and series_b must share the same date index"

    dates = series_a.index
    correlations = pd.Series(float("nan"), index=dates, dtype=float)

    for end_position in range(window - 1, len(dates)):
        start_position = end_position - window + 1
        window_a = series_a.iloc[start_position : end_position + 1]
        window_b = series_b.iloc[start_position : end_position + 1]

        if window_a.isna().any() or window_b.isna().any():
            continue

        ranked_a = window_a.rank().to_numpy()
        ranked_b = window_b.rank().to_numpy()

        end_date = dates[end_position]
        correlations.loc[end_date] = core_math.pearson_correlation(ranked_a, ranked_b)

    return correlations


def assert_pandas_and_hand_written_agree(pandas_series, hand_written_series, tolerance):
    """
    Check that the pandas and hand-written 90-day Pearson correlations
    agree within a small numerical tolerance.

    Why it exists: BUILD-SPEC section 6.3 requires this assertion
    explicitly -- two independently written implementations of the same
    calculation should produce the same numbers, within ordinary
    floating-point rounding.

    Parameters:
        pandas_series: pandas.Series, from rolling_pearson_pandas().
        hand_written_series: pandas.Series, from
            core_math.rolling_pearson_hand_written(). Same index as
            pandas_series.
        tolerance: float, the maximum allowed absolute difference.

    Returns:
        None.

    Raises:
        AssertionError, naming the first offending date, if any date's
        values differ by more than tolerance.
    """
    assert pandas_series.index.equals(hand_written_series.index), (
        "pandas_series and hand_written_series must share the same date index"
    )

    both_present = pandas_series.notna() & hand_written_series.notna()
    difference = (pandas_series - hand_written_series).abs()
    mismatches = difference[both_present & (difference > tolerance)]

    assert len(mismatches) == 0, (
        f"pandas and hand-written 90-day Pearson correlation disagree by more than "
        f"{tolerance} on {len(mismatches)} date(s), e.g. {mismatches.index[0].date()}: "
        f"pandas={pandas_series.loc[mismatches.index[0]]}, "
        f"hand_written={hand_written_series.loc[mismatches.index[0]]}"
    )


def build_all_rolling_correlations(panel):
    """
    Compute every pair/window/method combination BUILD-SPEC section 6.3
    requires and assemble them into one long-format table.

    Why it exists: this is the orchestration step -- for each pair in
    config.CORRELATION_PAIRS, computes 30-day Pearson (pandas only),
    90-day Pearson (both implementations, asserted to agree), and 90-day
    Spearman, matching the shape sql/schema.sql's rolling_correlations
    table expects. Also keeps the hand-written 90-day Pearson values in a
    second table, so analysis query 8 can reconcile them against the
    pandas-computed values already asserted to agree here -- BUILD-SPEC
    section 8's "join proving that the correlation values stored in
    SQLite match those computed in Pandas", done at the SQL level rather
    than only in-memory. See docs/decisions-log.md.

    Parameters:
        panel: pandas.DataFrame, the primary daily panel (panel_daily.parquet).

    Returns:
        Tuple of two pandas.DataFrame: (correlations_df,
        hand_written_check_df), both with columns date, pair, window,
        method, correlation, date formatted as 'YYYY-MM-DD' text.
        hand_written_check_df holds only the 90-day Pearson hand-written
        values, one row per pair.

    Raises:
        AssertionError if the pandas and hand-written 90-day Pearson
        values disagree by more than config.CORRELATION_TOLERANCE for any
        pair.
    """
    rows = []
    hand_written_check_rows = []

    for pair_label, (column_a, column_b) in config.CORRELATION_PAIRS.items():
        series_a = panel[column_a]
        series_b = panel[column_b]

        pearson_30d = rolling_pearson_pandas(series_a, series_b, config.CORRELATION_WINDOW_SHORT)
        print(
            f"[correlations] {pair_label} pearson {config.CORRELATION_WINDOW_SHORT}d (pandas): "
            f"{pearson_30d.notna().sum()} non-NaN values"
        )
        rows.append(
            pd.DataFrame(
                {
                    "date": pearson_30d.index,
                    "pair": pair_label,
                    "window": config.CORRELATION_WINDOW_SHORT,
                    "method": "pearson",
                    "correlation": pearson_30d.values,
                }
            )
        )

        pearson_90d_pandas = rolling_pearson_pandas(series_a, series_b, config.CORRELATION_WINDOW_HEADLINE)
        pearson_90d_hand_written = core_math.rolling_pearson_hand_written(
            series_a, series_b, config.CORRELATION_WINDOW_HEADLINE
        )
        assert_pandas_and_hand_written_agree(
            pearson_90d_pandas, pearson_90d_hand_written, config.CORRELATION_TOLERANCE
        )
        print(
            f"[correlations] {pair_label} pearson {config.CORRELATION_WINDOW_HEADLINE}d: "
            f"{pearson_90d_pandas.notna().sum()} non-NaN values, "
            f"pandas and hand-written agree within {config.CORRELATION_TOLERANCE}"
        )
        rows.append(
            pd.DataFrame(
                {
                    "date": pearson_90d_pandas.index,
                    "pair": pair_label,
                    "window": config.CORRELATION_WINDOW_HEADLINE,
                    "method": "pearson",
                    "correlation": pearson_90d_pandas.values,
                }
            )
        )
        hand_written_check_rows.append(
            pd.DataFrame(
                {
                    "date": pearson_90d_hand_written.index,
                    "pair": pair_label,
                    "window": config.CORRELATION_WINDOW_HEADLINE,
                    "method": "pearson",
                    "correlation": pearson_90d_hand_written.values,
                }
            )
        )

        spearman_90d = rolling_spearman(series_a, series_b, config.CORRELATION_WINDOW_HEADLINE)
        print(
            f"[correlations] {pair_label} spearman {config.CORRELATION_WINDOW_HEADLINE}d: "
            f"{spearman_90d.notna().sum()} non-NaN values"
        )
        rows.append(
            pd.DataFrame(
                {
                    "date": spearman_90d.index,
                    "pair": pair_label,
                    "window": config.CORRELATION_WINDOW_HEADLINE,
                    "method": "spearman",
                    "correlation": spearman_90d.values,
                }
            )
        )

    correlations_df = pd.concat(rows, ignore_index=True)
    correlations_df = correlations_df.dropna(subset=["correlation"]).reset_index(drop=True)
    correlations_df["date"] = pd.to_datetime(correlations_df["date"]).dt.strftime("%Y-%m-%d")
    print(f"[correlations] assembled {len(correlations_df)} total rolling_correlations rows")

    hand_written_check_df = pd.concat(hand_written_check_rows, ignore_index=True)
    hand_written_check_df = hand_written_check_df.dropna(subset=["correlation"]).reset_index(drop=True)
    hand_written_check_df["date"] = pd.to_datetime(hand_written_check_df["date"]).dt.strftime("%Y-%m-%d")
    print(f"[correlations] assembled {len(hand_written_check_df)} hand-written-check rows (query 8)")

    return correlations_df, hand_written_check_df


def main():
    """
    Compute all rolling correlations and load them into the already-built
    btc_regime.db.

    Why it exists: this is the entry point src/run_all.py calls for
    Phase 4 (BUILD-SPEC section 12). Opens its own connection to
    config.DB_PATH rather than rebuilding the database -- Phase 3
    (src/database.py) already created the schema and loaded the base
    tables.

    Parameters:
        None.

    Returns:
        None.
    """
    panel = load_panel()
    correlations_df, hand_written_check_df = build_all_rolling_correlations(panel)

    conn = sqlite3.connect(config.DB_PATH)
    try:
        database.load_dataframe_to_table(conn, correlations_df, "rolling_correlations")
        database.load_dataframe_to_table(
            conn, hand_written_check_df, "rolling_correlations_recomputed_check"
        )
        conn.commit()
    finally:
        conn.close()


if __name__ == "__main__":
    main()
    sys.exit(0)
