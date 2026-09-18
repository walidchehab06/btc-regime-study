"""
Tests for src/database.py's panel-to-SQLite melt logic and the
reconciliation query it must make pass, per BUILD-SPEC-bitcoin-regime-
study.md section 12 (Phase 3). All tests use a small hand-built panel with
the real config.MARKET_TICKERS/config.FRED_SERIES names -- no network
calls, no dependence on data/raw or data/processed.
"""

import numpy as np
import pandas as pd
import sqlite3

from src import config, database


def make_small_panel():
    """Build a 3-day panel with every real ticker/series column build_panel.py produces."""
    dates = pd.to_datetime(["2024-01-01", "2024-01-02", "2024-01-03"])
    data = {}

    for offset, ticker in enumerate(config.MARKET_TICKERS):
        base_price = 100.0 + offset
        close_prices = pd.Series([base_price, base_price * 1.01, base_price * 0.99])
        data[f"close_{ticker}"] = close_prices.values
        data[f"volume_{ticker}"] = [1000, 1100, 1050]
        data[f"log_return_{ticker}"] = np.log(close_prices / close_prices.shift(1)).values

    for offset, series_id in enumerate(config.FRED_SERIES):
        data[f"value_{series_id}"] = [1.0 + offset, 1.0 + offset, 1.0 + offset]
        data[f"is_forward_filled_{series_id}"] = [False, False, False]

    data["fng_value"] = [50.0, 60.0, 40.0]
    data["fng_label"] = ["Neutral", "Greed", "Fear"]

    panel = pd.DataFrame(data, index=dates)
    panel.index.name = "date"
    return panel


def test_build_prices_and_returns_long_has_one_row_per_ticker_per_date():
    panel = make_small_panel()
    prices_daily_df, returns_daily_df = database.build_prices_and_returns_long(panel)

    n_tickers = len(config.MARKET_TICKERS)
    assert len(prices_daily_df) == n_tickers * 3
    assert len(returns_daily_df) == n_tickers * 3
    assert list(prices_daily_df.columns) == ["date", "close", "volume", "ticker"]
    assert prices_daily_df["date"].iloc[0] == "2024-01-01"


def test_build_prices_and_returns_long_preserves_values_for_one_ticker():
    panel = make_small_panel()
    prices_daily_df, returns_daily_df = database.build_prices_and_returns_long(panel)

    one_ticker = next(iter(config.MARKET_TICKERS))
    ticker_prices = prices_daily_df[prices_daily_df["ticker"] == one_ticker].reset_index(drop=True)
    ticker_returns = returns_daily_df[returns_daily_df["ticker"] == one_ticker].reset_index(drop=True)

    assert ticker_prices["close"].iloc[0] == panel[f"close_{one_ticker}"].iloc[0]
    assert np.isnan(ticker_returns["log_return"].iloc[0])
    assert ticker_returns["log_return"].iloc[1] == panel[f"log_return_{one_ticker}"].iloc[1]


def test_build_macro_long_flags_forward_filled_as_integer():
    panel = make_small_panel()
    macro_daily_df = database.build_macro_long(panel)

    n_series = len(config.FRED_SERIES)
    assert len(macro_daily_df) == n_series * 3
    assert macro_daily_df["is_forward_filled"].dtype == int
    assert set(macro_daily_df["is_forward_filled"].unique()) <= {0, 1}


def test_build_sentiment_long_keeps_fng_columns():
    panel = make_small_panel()
    sentiment_daily_df = database.build_sentiment_long(panel)

    assert list(sentiment_daily_df.columns) == ["date", "fng_value", "fng_label"]
    assert list(sentiment_daily_df["fng_label"]) == ["Neutral", "Greed", "Fear"]


def test_build_returns_recomputed_check_matches_hand_computed_log_return():
    panel = make_small_panel()
    recomputed_df = database.build_returns_recomputed_check(panel)

    one_ticker = next(iter(config.MARKET_TICKERS))
    ticker_rows = recomputed_df[recomputed_df["ticker"] == one_ticker].reset_index(drop=True)

    close_day1 = panel[f"close_{one_ticker}"].iloc[0]
    close_day2 = panel[f"close_{one_ticker}"].iloc[1]

    assert np.isnan(ticker_rows["log_return"].iloc[0])
    assert ticker_rows["log_return"].iloc[1] == np.log(close_day2 / close_day1)


def test_split_analysis_queries_finds_every_query():
    sql_text = config.SQL_ANALYSIS_QUERIES_PATH.read_text()
    queries = database.split_analysis_queries(sql_text)

    assert len(queries) == len(config.ANALYSIS_QUERY_EXPORT_FILENAMES)
    for query_number, query_text in enumerate(queries, start=1):
        assert query_text.startswith(f"-- Query {query_number}:")


def test_reconciliation_query_passes_on_matching_data_and_fails_on_a_planted_mismatch():
    panel = make_small_panel()
    _, returns_daily_df = database.build_prices_and_returns_long(panel)
    recomputed_df = database.build_returns_recomputed_check(panel)

    query_text = database.split_analysis_queries(config.SQL_ANALYSIS_QUERIES_PATH.read_text())[6]

    conn = sqlite3.connect(":memory:")
    try:
        database.create_schema(conn)
        returns_daily_df.to_sql("returns_daily", conn, if_exists="append", index=False)
        recomputed_df.to_sql("returns_daily_recomputed_check", conn, if_exists="append", index=False)

        clean_result = pd.read_sql_query(query_text, conn)
        assert len(clean_result) == 0

        conn.execute(
            "UPDATE returns_daily_recomputed_check SET log_return = 999.0 "
            "WHERE date = '2024-01-02' AND ticker = ?",
            (next(iter(config.MARKET_TICKERS)),),
        )
        planted_mismatch_result = pd.read_sql_query(query_text, conn)
        assert len(planted_mismatch_result) == 1
    finally:
        conn.close()
