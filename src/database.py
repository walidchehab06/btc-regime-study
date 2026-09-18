"""
Build data/processed/btc_regime.db and run the analysis queries in
sql/analysis_queries.sql, per BUILD-SPEC-bitcoin-regime-study.md section 12
(Phase 3).

Why this file exists: this is where the wide panel_daily.parquet gets
turned into the long-format tables section 8 asks for, and where the
seven analysis queries actually get executed and exported to
outputs/tables/, so every number in the eventual write-up has a file
behind it.
"""

import math
import re
import sqlite3
import sys

import pandas as pd

from src import config


def load_panel():
    """
    Load the primary daily panel built in Phase 2.

    Why it exists: every table in this module is derived from the same
    source, panel_daily.parquet, so this is the one place that reads it.

    Parameters:
        None.

    Returns:
        pandas.DataFrame indexed by date (datetime), as saved by
        src/build_panel.py.
    """
    panel = pd.read_parquet(config.PANEL_PATH)
    print(f"[database] loaded {config.PANEL_PATH}: {len(panel)} rows, {len(panel.columns)} columns")
    return panel


def format_date_column(df, date_column="date"):
    """
    Convert a datetime column to the 'YYYY-MM-DD' text format used for
    every date column in the SQLite schema.

    Why it exists: sql/analysis_queries.sql relies on strftime() to pull
    the calendar year out of the date column (query 1), which only works
    if dates are stored as plain ISO text, not as pandas Timestamps.

    Parameters:
        df: pandas.DataFrame with a datetime-typed column named date_column.
        date_column: str, the column to convert.

    Returns:
        The same DataFrame, with date_column converted to string in place.
    """
    df[date_column] = df[date_column].dt.strftime("%Y-%m-%d")
    return df


def build_prices_and_returns_long(panel):
    """
    Melt the wide panel's close/volume/log_return columns into the long
    format prices_daily and returns_daily expect.

    Why it exists: BUILD-SPEC section 8 specifies prices_daily and
    returns_daily as long tables (date, ticker, ...), one row per
    ticker-day, which is a different shape from the wide
    close_<ticker>-style columns build_panel.py produces.

    Parameters:
        panel: pandas.DataFrame, the primary daily panel.

    Returns:
        Tuple of two pandas.DataFrame: (prices_daily_df, returns_daily_df),
        each with a date column already formatted as 'YYYY-MM-DD' text.
    """
    price_rows = []
    return_rows = []
    for ticker in config.MARKET_TICKERS:
        ticker_prices = panel[[f"close_{ticker}", f"volume_{ticker}"]].reset_index()
        ticker_prices.columns = ["date", "close", "volume"]
        ticker_prices["ticker"] = ticker
        price_rows.append(ticker_prices)

        ticker_returns = panel[[f"log_return_{ticker}"]].reset_index()
        ticker_returns.columns = ["date", "log_return"]
        ticker_returns["ticker"] = ticker
        return_rows.append(ticker_returns)

    prices_daily_df = pd.concat(price_rows, ignore_index=True)
    returns_daily_df = pd.concat(return_rows, ignore_index=True)

    format_date_column(prices_daily_df)
    format_date_column(returns_daily_df)
    return prices_daily_df, returns_daily_df


def build_macro_long(panel):
    """
    Melt the wide panel's value/is_forward_filled columns into the long
    format macro_daily expects.

    Why it exists: BUILD-SPEC section 8 specifies macro_daily as
    (date, series_id, value, is_forward_filled), a different shape from
    the wide value_<series_id>-style columns build_panel.py produces.

    Parameters:
        panel: pandas.DataFrame, the primary daily panel.

    Returns:
        pandas.DataFrame with columns date, series_id, value,
        is_forward_filled (0/1 integer), date formatted as 'YYYY-MM-DD' text.
    """
    macro_rows = []
    for series_id in config.FRED_SERIES:
        series_values = panel[[f"value_{series_id}", f"is_forward_filled_{series_id}"]].reset_index()
        series_values.columns = ["date", "value", "is_forward_filled"]
        series_values["series_id"] = series_id
        series_values["is_forward_filled"] = series_values["is_forward_filled"].astype(int)
        macro_rows.append(series_values)

    macro_daily_df = pd.concat(macro_rows, ignore_index=True)
    format_date_column(macro_daily_df)
    return macro_daily_df[["date", "series_id", "value", "is_forward_filled"]]


def build_sentiment_long(panel):
    """
    Extract the Fear & Greed columns into the shape sentiment_daily expects.

    Why it exists: sentiment_daily is already close to the wide panel's
    shape (one row per date), so this only needs a column rename and date
    formatting, unlike the ticker/series tables above.

    Parameters:
        panel: pandas.DataFrame, the primary daily panel.

    Returns:
        pandas.DataFrame with columns date, fng_value, fng_label, date
        formatted as 'YYYY-MM-DD' text.
    """
    sentiment_daily_df = panel[["fng_value", "fng_label"]].reset_index()
    sentiment_daily_df.columns = ["date", "fng_value", "fng_label"]
    format_date_column(sentiment_daily_df)
    return sentiment_daily_df


def build_returns_recomputed_check(panel):
    """
    Recompute every ticker's daily log return directly from close prices,
    using a plain row-by-row loop instead of build_panel.py's vectorized
    NumPy operation.

    Why it exists: analysis query 7's reconciliation check needs a second,
    independently written computation of the values stored in
    returns_daily, so that a bug in the vectorized melt in
    build_prices_and_returns_long() is unlikely to be reproduced
    identically here. See docs/decisions-log.md for why this replaces the
    correlation-value reconciliation the spec originally describes for
    this slot, which has to wait for Phase 4.

    Parameters:
        panel: pandas.DataFrame, the primary daily panel.

    Returns:
        pandas.DataFrame with columns date, ticker, log_return, date
        formatted as 'YYYY-MM-DD' text.
    """
    rows = []
    for ticker in config.MARKET_TICKERS:
        close_prices = panel[f"close_{ticker}"]
        previous_close = None
        for date, close_price in close_prices.items():
            if previous_close is None or pd.isna(previous_close) or pd.isna(close_price):
                log_return = float("nan")
            else:
                log_return = math.log(close_price / previous_close)
            rows.append({"date": date, "ticker": ticker, "log_return": log_return})
            previous_close = close_price

    recomputed_df = pd.DataFrame(rows)
    format_date_column(recomputed_df)
    return recomputed_df


def create_schema(conn, schema_path=config.SQL_SCHEMA_PATH):
    """
    Create every table and index defined in sql/schema.sql.

    Why it exists: keeps the CREATE TABLE statements themselves in one SQL
    file (sql/schema.sql) that a reviewer can read on its own, rather than
    embedding schema strings in Python.

    Parameters:
        conn: sqlite3.Connection, the open database connection.
        schema_path: pathlib.Path, defaults to config.SQL_SCHEMA_PATH.

    Returns:
        None.
    """
    schema_sql = schema_path.read_text()
    conn.executescript(schema_sql)
    print(f"[database] created schema from {schema_path}")


def load_dataframe_to_table(conn, df, table_name):
    """
    Insert a DataFrame's rows into a table, printing the row count before
    the insert and the table's row count after.

    Why it exists: CLAUDE.md requires row counts to be printed before and
    after every merge; loading a table is this project's equivalent step
    for the SQLite layer.

    Parameters:
        conn: sqlite3.Connection, the open database connection.
        df: pandas.DataFrame, the rows to insert.
        table_name: str, an existing table created by create_schema().

    Returns:
        None.
    """
    print(f"[database] {table_name}: {len(df)} rows before insert")
    df.to_sql(table_name, conn, if_exists="append", index=False)
    row_count_after = conn.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()[0]
    print(f"[database] {table_name}: {row_count_after} rows in table after insert")
    assert row_count_after == len(df), (
        f"{table_name}: expected {len(df)} rows after insert, found {row_count_after}. "
        "Some rows were silently dropped or duplicated on load."
    )


def split_analysis_queries(sql_text):
    """
    Split sql/analysis_queries.sql into the individual query texts, one
    per '-- Query N:' comment block.

    Why it exists: the seven queries need to be run and exported one at a
    time; this keeps the split logic in one place instead of hand-copying
    query text into Python.

    Parameters:
        sql_text: str, the full contents of sql/analysis_queries.sql.

    Returns:
        List of str, one complete query (including its leading English
        comment) per list item, in file order.
    """
    first_query_start = sql_text.index("-- Query 1:")
    body = sql_text[first_query_start:]
    query_start_pattern = re.compile(r"(?=-- Query \d+:)")
    raw_blocks = query_start_pattern.split(body)
    queries = [block.strip() for block in raw_blocks if block.strip()]
    return queries


def run_analysis_queries_and_export(conn):
    """
    Run every query in sql/analysis_queries.sql and write its result to
    outputs/tables/ as a CSV.

    Why it exists: BUILD-SPEC section 8 requires every analysis query's
    result to be exported so it has a file behind it. Also enforces that
    query 7 (the reconciliation check) actually returns zero mismatches,
    per section 12's Phase 3 acceptance criterion.

    Parameters:
        conn: sqlite3.Connection, the open, already-loaded database connection.

    Returns:
        None.

    Raises:
        AssertionError if the reconciliation query (query 7) finds any
        mismatch above config.RECONCILIATION_TOLERANCE.
    """
    config.OUTPUTS_TABLES_DIR.mkdir(parents=True, exist_ok=True)
    sql_text = config.SQL_ANALYSIS_QUERIES_PATH.read_text()
    queries = split_analysis_queries(sql_text)

    assert len(queries) == len(config.ANALYSIS_QUERY_EXPORT_FILENAMES), (
        f"found {len(queries)} queries in {config.SQL_ANALYSIS_QUERIES_PATH}, "
        f"expected {len(config.ANALYSIS_QUERY_EXPORT_FILENAMES)}"
    )

    for query_number, (query_text, export_filename) in enumerate(
        zip(queries, config.ANALYSIS_QUERY_EXPORT_FILENAMES), start=1
    ):
        result_df = pd.read_sql_query(query_text, conn)
        export_path = config.OUTPUTS_TABLES_DIR / export_filename
        result_df.to_csv(export_path, index=False)
        print(f"[database] query {query_number}: {len(result_df)} rows -> {export_path}")

        if query_number == 7:
            assert len(result_df) == 0, (
                "query 7 (reconciliation check) found "
                f"{len(result_df)} mismatched log-return value(s) between the ETL "
                "load and the independently recomputed check table -- see "
                f"{export_path} for which ones. Investigate before proceeding."
            )
            print("[database] query 7 (reconciliation check) passed: 0 mismatches")


def main():
    """
    Build data/processed/btc_regime.db from panel_daily.parquet and run
    the analysis queries.

    Why it exists: this is the entry point src/run_all.py calls for
    Phase 3 (BUILD-SPEC section 12).

    Parameters:
        None.

    Returns:
        None.
    """
    config.PROCESSED_DATA_DIR.mkdir(parents=True, exist_ok=True)
    if config.DB_PATH.exists():
        config.DB_PATH.unlink()
        print(f"[database] removed existing {config.DB_PATH} -- rebuilding from panel_daily.parquet")

    panel = load_panel()

    conn = sqlite3.connect(config.DB_PATH)
    try:
        create_schema(conn)

        prices_daily_df, returns_daily_df = build_prices_and_returns_long(panel)
        load_dataframe_to_table(conn, prices_daily_df, "prices_daily")
        load_dataframe_to_table(conn, returns_daily_df, "returns_daily")

        macro_daily_df = build_macro_long(panel)
        load_dataframe_to_table(conn, macro_daily_df, "macro_daily")

        sentiment_daily_df = build_sentiment_long(panel)
        load_dataframe_to_table(conn, sentiment_daily_df, "sentiment_daily")

        recomputed_returns_df = build_returns_recomputed_check(panel)
        load_dataframe_to_table(conn, recomputed_returns_df, "returns_daily_recomputed_check")

        print(
            "[database] rolling_correlations, regimes, and regime_periods created "
            "empty -- populated in Phase 4 and Phase 5 (see docs/decisions-log.md)"
        )

        conn.commit()
        run_analysis_queries_and_export(conn)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
    sys.exit(0)
