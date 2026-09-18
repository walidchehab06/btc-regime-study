"""
Validation against published institutional correlation figures, per
BUILD-SPEC-bitcoin-regime-study.md section 3 and section 12 (Phase 6).

Why this file exists: section 3 requires this repo to compute its own
90-day BTC-Nasdaq and BTC-gold correlations and compare them against a
handful of externally published readings (Grayscale, Bitwise), with a
stated delta and a real methodological reason for any difference -- not a
vague one. The published figures and their citations are collected in
docs/sources.md; this module is where the comparison itself gets computed
and written to outputs/tables/validation_comparison.csv, which
docs/validation.md and figure 10 both read from.
"""

import sys

import pandas as pd
import sqlite3

from src import config, core_math, correlations, database


def compute_validation_correlations(panel):
    """
    Compute the 90-day Pearson correlation for every pair in
    config.VALIDATION_CORRELATION_PAIRS.

    Why it exists: BTC vs Nasdaq-100 (^NDX) and BTC vs gold futures (GC=F)
    are the alternate-instrument series needed to test whether an index or
    instrument choice explains a published-figure discrepancy. Reuses the
    same pandas and hand-written implementations and the same agreement
    check src/correlations.py already proved correct in Phase 4, applied
    to different columns.

    Parameters:
        panel: pandas.DataFrame, the primary daily panel (panel_daily.parquet).

    Returns:
        pandas.DataFrame with columns date, pair, window, method,
        correlation, date formatted as 'YYYY-MM-DD' text -- same shape as
        rolling_correlations.

    Raises:
        AssertionError if the pandas and hand-written 90-day Pearson
        values disagree by more than config.CORRELATION_TOLERANCE for any
        pair.
    """
    rows = []

    for pair_label, (column_a, column_b) in config.VALIDATION_CORRELATION_PAIRS.items():
        series_a = panel[column_a]
        series_b = panel[column_b]

        pearson_90d_pandas = correlations.rolling_pearson_pandas(
            series_a, series_b, config.CORRELATION_WINDOW_HEADLINE
        )
        pearson_90d_hand_written = core_math.rolling_pearson_hand_written(
            series_a, series_b, config.CORRELATION_WINDOW_HEADLINE
        )
        correlations.assert_pandas_and_hand_written_agree(
            pearson_90d_pandas, pearson_90d_hand_written, config.CORRELATION_TOLERANCE
        )
        print(
            f"[validation] {pair_label} pearson {config.CORRELATION_WINDOW_HEADLINE}d: "
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

    validation_correlations_df = pd.concat(rows, ignore_index=True)
    validation_correlations_df = validation_correlations_df.dropna(subset=["correlation"]).reset_index(drop=True)
    validation_correlations_df["date"] = pd.to_datetime(validation_correlations_df["date"]).dt.strftime("%Y-%m-%d")
    print(f"[validation] assembled {len(validation_correlations_df)} rolling_correlations_validation rows")
    return validation_correlations_df


def load_comparison_input_correlations(conn):
    """
    Load every pair build_comparison_rows() might need to look up: the
    headline pairs from rolling_correlations (Phase 4) and the alternate-
    instrument pairs from rolling_correlations_validation, at the 90-day
    Pearson window only.

    Why it exists: build_comparison_rows() takes one combined DataFrame so
    it stays pure (no DB connection of its own) and easy to unit test.

    Parameters:
        conn: sqlite3.Connection, open connection to btc_regime.db.

    Returns:
        pandas.DataFrame with columns date, pair, window, method,
        correlation -- date as 'YYYY-MM-DD' text, the same format
        published_as_of_date uses in config.PUBLISHED_VALIDATION_FIGURES.
    """
    headline_pairs = list(config.CORRELATION_PAIRS)
    validation_pairs = list(config.VALIDATION_CORRELATION_PAIRS)

    headline_query = (
        "SELECT date, pair, window, method, correlation FROM rolling_correlations "
        "WHERE window = ? AND method = 'pearson' AND pair IN ({})".format(
            ",".join("?" for _ in headline_pairs)
        )
    )
    headline_df = pd.read_sql_query(
        headline_query, conn, params=[config.CORRELATION_WINDOW_HEADLINE, *headline_pairs]
    )

    validation_query = (
        "SELECT date, pair, window, method, correlation FROM rolling_correlations_validation "
        "WHERE window = ? AND method = 'pearson' AND pair IN ({})".format(
            ",".join("?" for _ in validation_pairs)
        )
    )
    validation_df = pd.read_sql_query(
        validation_query, conn, params=[config.CORRELATION_WINDOW_HEADLINE, *validation_pairs]
    )

    print(
        f"[validation] loaded {len(headline_df)} rows from rolling_correlations, "
        f"{len(validation_df)} rows from rolling_correlations_validation"
    )
    return pd.concat([headline_df, validation_df], ignore_index=True)


def build_comparison_rows(correlations_long_df, published_figures):
    """
    Build one comparison row per published figure: the published value,
    our computed value on the same date, the delta, and (where
    applicable) a robustness-check value against an alternate instrument.

    Why it exists: this is the pure core of the validation comparison --
    no I/O, so it can be unit tested directly with a small synthetic
    correlations_long_df, and safely reused by both build_comparison_table()
    and the pytest suite.

    Parameters:
        correlations_long_df: pandas.DataFrame with columns date, pair,
            correlation (window/method already filtered to 90-day
            Pearson), e.g. from load_comparison_input_correlations().
        published_figures: list of dict, e.g.
            config.PUBLISHED_VALIDATION_FIGURES -- each with keys
            comparison_id, metric_label, publisher, published_value,
            published_as_of_date, primary_computed_pair,
            robustness_computed_pair, explanation_key.

    Returns:
        pandas.DataFrame, one row per entry in published_figures, columns
        comparison_id, publisher, metric_label, published_value,
        published_as_of_date, computed_pair, computed_value, delta,
        robustness_pair, robustness_value, robustness_delta, explanation.
        robustness_pair/robustness_value/robustness_delta are None when
        the entry's robustness_computed_pair is None.

    Raises:
        ValueError, naming the missing pair and date, if a required
        (pair, date) combination is not present in correlations_long_df --
        never silently substituted with a nearby date or NaN.
    """

    def lookup(pair, date):
        matches = correlations_long_df[
            (correlations_long_df["pair"] == pair) & (correlations_long_df["date"] == date)
        ]
        if len(matches) == 0:
            raise ValueError(f"no correlation found for pair={pair!r} on date={date!r}")
        return float(matches["correlation"].iloc[0])

    rows = []
    for figure in published_figures:
        as_of_date = figure["published_as_of_date"]
        computed_value = lookup(figure["primary_computed_pair"], as_of_date)
        delta = computed_value - figure["published_value"]

        robustness_pair = figure["robustness_computed_pair"]
        if robustness_pair is not None:
            robustness_value = lookup(robustness_pair, as_of_date)
            robustness_delta = robustness_value - figure["published_value"]
        else:
            robustness_value = None
            robustness_delta = None

        rows.append(
            {
                "comparison_id": figure["comparison_id"],
                "publisher": figure["publisher"],
                "metric_label": figure["metric_label"],
                "published_value": figure["published_value"],
                "published_as_of_date": as_of_date,
                "computed_pair": figure["primary_computed_pair"],
                "computed_value": computed_value,
                "delta": delta,
                "robustness_pair": robustness_pair,
                "robustness_value": robustness_value,
                "robustness_delta": robustness_delta,
                "explanation": config.VALIDATION_EXPLANATION_TEXT[figure["explanation_key"]],
            }
        )

    return pd.DataFrame(rows)


def build_comparison_table(conn):
    """
    Load the correlations build_comparison_rows() needs, build the
    comparison table, and write it to
    config.VALIDATION_COMPARISON_TABLE_PATH.

    Why it exists: the orchestration step between the pure comparison
    logic and the on-disk table docs/validation.md and figure 10 both
    read from.

    Parameters:
        conn: sqlite3.Connection, open connection to btc_regime.db.

    Returns:
        pandas.DataFrame, the same comparison table that was written to
        config.VALIDATION_COMPARISON_TABLE_PATH.
    """
    correlations_long_df = load_comparison_input_correlations(conn)
    comparison_df = build_comparison_rows(correlations_long_df, config.PUBLISHED_VALIDATION_FIGURES)

    config.OUTPUTS_TABLES_DIR.mkdir(parents=True, exist_ok=True)
    comparison_df.to_csv(config.VALIDATION_COMPARISON_TABLE_PATH, index=False)
    print(f"[validation] wrote {len(comparison_df)} rows -> {config.VALIDATION_COMPARISON_TABLE_PATH}")
    return comparison_df


def main():
    """
    Compute the Phase 6 validation correlations, load them into the
    already-built btc_regime.db, and build the published-vs-computed
    comparison table.

    Why it exists: this is the entry point src/run_all.py calls for
    Phase 6 (BUILD-SPEC section 12). Opens its own connection to
    config.DB_PATH, same pattern as correlations.main() and regimes.main()
    -- Phase 3 already created the schema, and Phase 4 has already loaded
    rolling_correlations, which build_comparison_table() reads from.

    Parameters:
        None.

    Returns:
        None.
    """
    panel = correlations.load_panel()
    validation_correlations_df = compute_validation_correlations(panel)

    conn = sqlite3.connect(config.DB_PATH)
    try:
        database.load_dataframe_to_table(conn, validation_correlations_df, "rolling_correlations_validation")
        conn.commit()
        build_comparison_table(conn)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
    sys.exit(0)
