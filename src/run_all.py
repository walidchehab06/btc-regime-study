"""
Single-command entry point for the full pipeline: `python -m src.run_all`.

Why this file exists: we're on Windows without `make` installed, so this
module replaces the Makefile BUILD-SPEC-bitcoin-regime-study.md section 7
mentions as an option. See docs/decisions-log.md for the reasoning. Each
phase of the pipeline (BUILD-SPEC section 12) adds its step here, in order.
"""

import sqlite3
import sys

from src import (
    build_panel,
    charts,
    config,
    correlations,
    database,
    fetch_fred,
    fetch_market,
    fetch_sentiment,
    model,
    regimes,
    sentiment,
    validation,
)


def run_phase_1_data_acquisition():
    """
    Run every fetch step for Phase 1: market prices, FRED macro series, sentiment.

    Why it exists: groups the three independent fetch modules into the one
    pipeline step BUILD-SPEC section 12 calls "Phase 1 - Data acquisition".

    Parameters:
        None.

    Returns:
        None.
    """
    print("=== Phase 1: Data acquisition ===")

    print("--- Market prices (yfinance) ---")
    fetch_market.fetch_all_tickers()

    print("--- Macro series (FRED) ---")
    fetch_fred.fetch_all_series()

    print("--- Sentiment (Fear & Greed Index) ---")
    fetch_sentiment.fetch_and_cache_sentiment()


def run_phase_2_panel_construction():
    """
    Run the panel-construction step for Phase 2.

    Why it exists: groups build_panel.main() under the name BUILD-SPEC
    section 12 calls "Phase 2 - Panel construction".

    Parameters:
        None.

    Returns:
        None.
    """
    print("=== Phase 2: Panel construction ===")
    build_panel.main()


def run_phase_3_sqlite():
    """
    Run the SQLite build-and-query step for Phase 3.

    Why it exists: groups database.main() under the name BUILD-SPEC
    section 12 calls "Phase 3 - SQLite".

    Parameters:
        None.

    Returns:
        None.
    """
    print("=== Phase 3: SQLite ===")
    database.main()


def run_phase_4_correlations():
    """
    Run the rolling-correlation step for Phase 4.

    Why it exists: groups correlations.main() under the name BUILD-SPEC
    section 12 calls "Phase 4 - Correlations". Runs after Phase 3 has
    created the schema and loaded the base tables, since correlations.py
    opens its own connection to the already-built database rather than
    rebuilding it. Figure generation moved out of this step and into
    run_charts(), which now runs after Phase 5 -- figure 1's regime
    bands and figures 3 and 5 need regime_periods, which doesn't exist
    until Phase 5 loads it. See docs/decisions-log.md.

    Parameters:
        None.

    Returns:
        None.
    """
    print("=== Phase 4: Correlations ===")
    correlations.main()


def run_phase_5_regimes():
    """
    Run the regime-classification step for Phase 5.

    Why it exists: groups regimes.main() under the name BUILD-SPEC
    section 12 calls "Phase 5 - Regimes". Runs after Phase 4 has loaded
    rolling_correlations, since regimes.py classifies regimes from the
    90-day Pearson BTC_NASDAQ and BTC_GOLD correlations Phase 4 computed.

    Parameters:
        None.

    Returns:
        None.
    """
    print("=== Phase 5: Regimes ===")
    regimes.main()


def run_phase_6_validation():
    """
    Run the validation step for Phase 6.

    Why it exists: groups validation.main() under the name BUILD-SPEC
    section 12 calls "Phase 6 - Validation". Runs after Phase 5 has
    loaded rolling_correlations, which validation.py's comparison table
    reads from, and before run_charts(), which needs
    outputs/tables/validation_comparison.csv to exist for figure 10.

    Parameters:
        None.

    Returns:
        None.
    """
    print("=== Phase 6: Validation ===")
    validation.main()


def run_phase_7_sentiment():
    """
    Run the sentiment-analysis step for Phase 7.

    Why it exists: groups sentiment.main() under the name BUILD-SPEC
    section 12 calls "Phase 7 - Sentiment". Runs after Phase 5 has loaded
    the regimes table, which sentiment.py's transition-proximity check
    reads, and before run_charts(), which needs
    outputs/tables/sentiment_forward_returns_daily.csv for figure 7.

    Parameters:
        None.

    Returns:
        None.
    """
    print("=== Phase 7: Sentiment ===")
    sentiment.main()


def run_phase_8_model():
    """
    Run the ML classifier step for Phase 8.

    Why it exists: groups model.main() under the name BUILD-SPEC section
    12 calls "Phase 8 - Model". Runs after Phase 5 has loaded regimes and
    Phase 4 has loaded rolling_correlations, both of which
    src/model.py's feature matrix reads, and before run_charts(), since
    model.main() renders figures 8 and 9 itself (see
    src/charts.py:main()'s docstring) rather than waiting for
    run_charts() to do it.

    Parameters:
        None.

    Returns:
        None.
    """
    print("=== Phase 8: Model ===")
    model.main()


def run_charts():
    """
    Generate every figure, once every table the figures depend on has
    been loaded.

    Why it exists: figure 1's regime bands and figures 3 and 5 need
    regime_periods and outputs/tables/sensitivity_grid.csv, both from
    Phase 5, figure 10 needs outputs/tables/validation_comparison.csv
    from Phase 6, and figure 7 needs
    outputs/tables/sentiment_forward_returns_daily.csv from Phase 7, so
    chart generation moved here from inside run_phase_4_correlations() --
    the same reasoning as run_analysis_queries() moving out of Phase 3.
    Figures 8 and 9 are not generated here -- see
    run_phase_8_model()'s docstring. See docs/decisions-log.md.

    Parameters:
        None.

    Returns:
        None.
    """
    print("=== Generating figures ===")
    charts.main()


def run_analysis_queries():
    """
    Run and export every analysis query, once every table the queries
    depend on has been loaded.

    Why it exists: src/database.py's query-export step was pulled out of
    Phase 3 so it runs after Phase 4 (and, later, Phase 5) have populated
    rolling_correlations and regimes/regime_periods -- otherwise queries
    1, 2, 4, 5, 6, and 8 would run vacuously against empty tables. See
    docs/decisions-log.md.

    Parameters:
        None.

    Returns:
        None.
    """
    print("=== Exporting analysis query results ===")
    conn = sqlite3.connect(config.DB_PATH)
    try:
        database.run_analysis_queries_and_export(conn)
    finally:
        conn.close()


def main():
    """
    Run the full pipeline, phase by phase.

    Why it exists: the one command a clean clone of this repo needs to run,
    per BUILD-SPEC section 12's "definition of done" for the whole project.

    Parameters:
        None.

    Returns:
        None.
    """
    run_phase_1_data_acquisition()
    run_phase_2_panel_construction()
    run_phase_3_sqlite()
    run_phase_4_correlations()
    run_phase_5_regimes()
    run_phase_6_validation()
    run_phase_7_sentiment()
    run_phase_8_model()
    run_charts()
    run_analysis_queries()


if __name__ == "__main__":
    main()
    sys.exit(0)
