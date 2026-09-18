"""
Central place for every tunable value used by the data-acquisition pipeline.

Why this file exists: BUILD-SPEC-bitcoin-regime-study.md section 11 requires
that all tunable parameters (dates, tickers, series IDs, file paths) live
here and nowhere else, so that changing one of them is a one-line edit
instead of a search through every module.
"""

from pathlib import Path

# --- Study window (BUILD-SPEC section 5.1) ---
# 2018-02-01 is the day the Fear & Greed Index history begins, so every
# other series is pulled from the same start date for a common baseline.
STUDY_START_DATE = "2018-02-01"

# --- Market prices, pulled via yfinance (BUILD-SPEC section 5.1) ---
# Ticker -> role in the analysis, used for logging and for docs/data-dictionary.md.
MARKET_TICKERS = {
    "BTC-USD": "Bitcoin - the subject of the study",
    "^IXIC": "Nasdaq Composite - risk-asset / tech-equity benchmark, also the calendar anchor",
    "^NDX": "Nasdaq 100 - secondary equity benchmark, used for the validation comparison",
    "GC=F": "Gold futures - hard-asset benchmark",
    "GLD": "Gold ETF - robustness check against GC=F (different trading hours)",
    "DX-Y.NYB": "US Dollar Index - dollar-strength driver",
    "^GSPC": "S&P 500 - broad-equity control",
    "^VIX": "CBOE Volatility Index - risk-sentiment control",
}

# --- Macro series, pulled from FRED (BUILD-SPEC section 5.2) ---
# Series ID -> what it is, used for logging and for docs/data-dictionary.md.
FRED_SERIES = {
    "DFII10": "10-year Treasury inflation-indexed (real) yield",
    "DTWEXBGS": "Nominal Broad US Dollar Index",
    "M2SL": "M2 money supply (monthly, forward-filled into the daily panel)",
    "WALCL": "Fed balance sheet, total assets (weekly, forward-filled into the daily panel)",
    "T10Y2Y": "10y-2y Treasury spread",
}
FRED_BASE_URL = "https://api.stlouisfed.org/fred/series/observations"
FRED_API_KEY_ENV_VAR = "FRED_API_KEY"

# --- Sentiment, pulled from alternative.me (BUILD-SPEC section 5.3) ---
SENTIMENT_URL = "https://api.alternative.me/fng/?limit=0&format=json"
SENTIMENT_SERIES_NAME = "crypto_fear_greed_index"

# --- Source labels used consistently across fetch modules and the manifest ---
SOURCE_YFINANCE = "yfinance"
SOURCE_FRED = "fred"
SOURCE_SENTIMENT = "alternative_me"

# --- Caching and provenance (BUILD-SPEC section 5.4) ---
RAW_DATA_DIR = Path("data/raw")
MANIFEST_PATH = RAW_DATA_DIR / "_manifest.json"

# --- Panel construction (BUILD-SPEC section 6.1, 6.2, 5.2) ---
PROCESSED_DATA_DIR = Path("data/processed")
PANEL_PATH = PROCESSED_DATA_DIR / "panel_daily.parquet"
# The section 6.1 robustness-check panel: Bitcoin's weekend returns dropped
# instead of absorbed into Monday's return. Every other column is identical
# to panel_daily.parquet.
PANEL_ALT_WEEKEND_PATH = PROCESSED_DATA_DIR / "panel_daily_alt_weekend.parquet"

# The ticker whose trading days define the panel's date index (section 6.1).
CALENDAR_ANCHOR_TICKER = "^IXIC"

# FRED series that are monthly/weekly and therefore forward-filled into the
# daily panel, per section 5.2. Every other FRED series is left as NaN on
# days it hasn't been published yet, rather than filled.
FRED_FORWARD_FILL_SERIES = {"M2SL", "WALCL"}

# Daily FRED series (Treasury-derived) are NaN on bond-market holidays that
# aren't Nasdaq holidays -- Columbus Day and Veterans Day observed every
# year in the data, plus a handful of bond-market-only early closes. This
# caps how much of a daily FRED column can be NaN before build_panel.py
# treats it as a real gap instead of an expected holiday-calendar mismatch.
FRED_DAILY_MAX_NAN_FRACTION = 0.05

# --- SQLite layer (BUILD-SPEC section 8, section 12 Phase 3) ---
DB_PATH = PROCESSED_DATA_DIR / "btc_regime.db"
SQL_DIR = Path("sql")
SQL_SCHEMA_PATH = SQL_DIR / "schema.sql"
SQL_ANALYSIS_QUERIES_PATH = SQL_DIR / "analysis_queries.sql"
OUTPUTS_TABLES_DIR = Path("outputs/tables")

# Query 7 (the reconciliation check) treats two log-return values as a
# genuine mismatch only above this tolerance, to allow for ordinary
# floating-point rounding rather than a real data-integrity problem.
RECONCILIATION_TOLERANCE = 1e-9

# Filenames the analysis queries in sql/analysis_queries.sql export to, in
# the same order the queries appear in that file. Keeping the list here,
# rather than inline in database.py, follows section 11's rule that no
# output naming is left as a magic string buried in analysis code. Query 8
# (the rolling-correlation reconciliation) was added in Phase 4 -- see
# docs/decisions-log.md.
ANALYSIS_QUERY_EXPORT_FILENAMES = [
    "query_01_avg_correlation_by_year.csv",
    "query_02_largest_btc_gold_correlation_moves.csv",
    "query_03_forward_returns_by_sentiment_bucket.csv",
    "query_04_regime_duration_and_count.csv",
    "query_05_correlation_crossover_days.csv",
    "query_06_btc_volatility_by_regime.csv",
    "query_07_returns_reconciliation_check.csv",
    "query_08_correlation_reconciliation_check.csv",
]

# --- Rolling correlations (BUILD-SPEC section 6.3, section 12 Phase 4) ---
# Trading-day window lengths. 90 is the headline window (section 6.3: it
# matches most published institutional figures); 30 is shown alongside it
# to demonstrate how much the window choice matters (figure 2).
CORRELATION_WINDOW_SHORT = 30
CORRELATION_WINDOW_HEADLINE = 90

# Pair label -> (series_a column, series_b column) in panel_daily.parquet.
# Labels match the strings sql/analysis_queries.sql's queries 1, 2, 5, and 8
# already filter on. BTC_GOLD uses GLD, not GC=F: GLD trades on the same
# Nasdaq-anchored calendar as the rest of the panel, while GC=F futures
# trade different hours -- see docs/decisions-log.md. GC=F remains
# available as the section 5.1 robustness check, computed separately in
# Phase 6 validation under a different pair label.
CORRELATION_PAIRS = {
    "BTC_NASDAQ": ("log_return_BTC-USD", "log_return_^IXIC"),
    "BTC_GOLD": ("log_return_BTC-USD", "log_return_GLD"),
    "BTC_DXY": ("log_return_BTC-USD", "log_return_DX-Y.NYB"),
}

# The pair figure 2 (window-sensitivity) plots: the one the published
# comparisons in BUILD-SPEC section 3 center on.
WINDOW_SENSITIVITY_PAIR = "BTC_NASDAQ"

# Query 7's RECONCILIATION_TOLERANCE is scoped to the Phase 3 returns
# check; this is a separate constant because correlation values go through
# more floating-point operations (covariance, two standard deviations)
# than a single log-return recomputation, so a distinct tolerance is worth
# being able to tune independently -- see docs/decisions-log.md.
CORRELATION_TOLERANCE = 1e-9

# --- Charts (BUILD-SPEC section 9) ---
OUTPUTS_FIGURES_DIR = Path("outputs/figures")
FIGURE_DPI = 150
