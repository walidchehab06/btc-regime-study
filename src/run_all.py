"""
Single-command entry point for the full pipeline: `python -m src.run_all`.

Why this file exists: we're on Windows without `make` installed, so this
module replaces the Makefile BUILD-SPEC-bitcoin-regime-study.md section 7
mentions as an option. See docs/decisions-log.md for the reasoning. Each
phase of the pipeline (BUILD-SPEC section 12) adds its step here, in order.
"""

import sys

from src import build_panel, fetch_fred, fetch_market, fetch_sentiment


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


if __name__ == "__main__":
    main()
    sys.exit(0)
