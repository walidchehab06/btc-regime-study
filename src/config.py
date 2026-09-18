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
# (the rolling-correlation reconciliation) was added in Phase 4; query 9
# (the regime timeline) was added in Phase 5; query 10 (the sentiment x
# regime crosstab) was added in Phase 7 -- see docs/decisions-log.md.
ANALYSIS_QUERY_EXPORT_FILENAMES = [
    "query_01_avg_correlation_by_year.csv",
    "query_02_largest_btc_gold_correlation_moves.csv",
    "query_03_forward_returns_by_sentiment_bucket.csv",
    "query_04_regime_duration_and_count.csv",
    "query_05_correlation_crossover_days.csv",
    "query_06_btc_volatility_by_regime.csv",
    "query_07_returns_reconciliation_check.csv",
    "query_08_correlation_reconciliation_check.csv",
    "query_09_regime_timeline.csv",
    "query_10_sentiment_regime_crosstab.csv",
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

# --- Regime classification (BUILD-SPEC section 6.4, section 12 Phase 5) ---
# Baseline thresholds are a starting proposal per section 6.4 and are
# stress-tested by the section 6.5 sensitivity grid below, not treated as
# fixed truth.
REGIME_NASDAQ_THRESHOLD = 0.40
REGIME_GOLD_THRESHOLD = 0.35
REGIME_IDIOSYNCRATIC_THRESHOLD = 0.25

# A daily label run only survives as its own regime period if it holds for
# at least this many consecutive trading days (section 6.4). Shorter runs
# are merged into the surrounding regime -- see
# src/regimes.py:apply_persistence_filter() and docs/decisions-log.md for
# the merge-direction rule.
REGIME_PERSISTENCE_MIN_DAYS = 15

REGIME_LABEL_RISK_ASSET = "RISK_ASSET"
REGIME_LABEL_HARD_ASSET = "HARD_ASSET"
REGIME_LABEL_IDIOSYNCRATIC = "IDIOSYNCRATIC"
REGIME_LABEL_MIXED = "MIXED"

# Used to annualize Bitcoin's per-regime return and volatility
# (src/core_math.py). Matches the 252.0 literal already used in
# sql/analysis_queries.sql query 6; kept as a separate Python constant
# rather than parsed out of the SQL file, per section 11's one-tunable-
# per-value rule for analysis code (SQL text is not Python analysis code).
TRADING_DAYS_PER_YEAR = 252

# --- Sensitivity analysis (BUILD-SPEC section 6.5, mandatory) ---
SENSITIVITY_NASDAQ_THRESHOLDS = [0.30, 0.35, 0.40, 0.45, 0.50]
SENSITIVITY_GOLD_THRESHOLDS = [0.25, 0.30, 0.35, 0.40, 0.45]

# --- Charts (BUILD-SPEC section 9) ---
OUTPUTS_FIGURES_DIR = Path("outputs/figures")
FIGURE_DPI = 150

# --- Phase 5 output tables, written directly by src/regimes.py rather
# than through sql/analysis_queries.sql -- see docs/decisions-log.md for
# why these three are Python-computed instead of SQL-exported. ---
REGIME_SUMMARY_STATS_TABLE_PATH = OUTPUTS_TABLES_DIR / "regime_summary_statistics.csv"
SENSITIVITY_GRID_TABLE_PATH = OUTPUTS_TABLES_DIR / "sensitivity_grid.csv"
REGIME_LABEL_STABILITY_TABLE_PATH = OUTPUTS_TABLES_DIR / "regime_label_stability_before_after.csv"

# --- Validation (BUILD-SPEC section 3, section 12 Phase 6) ---
# The two alternate series CORRELATION_PAIRS' comment already points to:
# Nasdaq-100 in place of Nasdaq Composite, gold futures in place of the
# GLD ETF. Computed only at CORRELATION_WINDOW_HEADLINE (90 days) -- these
# exist to test a specific published-figure discrepancy on a specific
# date, not to be a second set of headline series, so there's no 30-day or
# Spearman variant. Kept out of CORRELATION_PAIRS/rolling_correlations
# entirely -- see docs/decisions-log.md for why they get their own table.
VALIDATION_CORRELATION_PAIRS = {
    "BTC_NASDAQ_NDX": ("log_return_BTC-USD", "log_return_^NDX"),
    "BTC_GOLD_GCF": ("log_return_BTC-USD", "log_return_GC=F"),
}

# One fixed sentence per methodological reason a computed correlation
# differs from a published one -- BUILD-SPEC section 3's list of known
# legitimate causes, applied to the specific comparisons below. Kept here,
# not written inline in src/validation.py, so every explanation string is
# a config-level fact instead of a literal buried in code (section 11).
VALIDATION_EXPLANATION_TEXT = {
    "nasdaq_index_and_vendor_ambiguity": (
        "The cited article does not say whether Grayscale used the Nasdaq "
        "Composite (^IXIC, our headline series) or the Nasdaq-100; it also "
        "does not state which data vendor or exact as-of date Grayscale's "
        "own figure is computed from, so some of this gap is unexplained "
        "vendor/window ambiguity rather than a named methodological choice."
    ),
    "gold_vendor_and_window_ambiguity": (
        "The cited article does not state which gold price series "
        "(spot, futures, or an ETF) or which data vendor Grayscale's "
        "figure is computed from, nor its exact as-of date -- our GLD-based "
        "series is one reasonable reading among several, not a forced match."
    ),
    "gold_etf_vs_futures": (
        "Bitwise's reported figure is not tied to a named instrument; GLD "
        "(our headline series) and GC=F (gold futures) trade different "
        "hours and can diverge on a given day's correlation reading -- the "
        "robustness-check column shows whether GC=F lands closer."
    ),
    "nasdaq_composite_vs_100": (
        "Bitwise's figure is explicitly reported against the Nasdaq-100, "
        "while our headline BTC_NASDAQ series uses the Nasdaq Composite "
        "(^IXIC) -- the robustness-check column recomputes the same day "
        "against the Nasdaq-100 to test whether that accounts for the gap."
    ),
}

# One dict per published claim being reproduced in docs/validation.md.
# published_as_of_date is the date the source's own underlying data ends
# (not the date the article was published), per the owner-confirmed
# reading of "as-of" -- see docs/decisions-log.md. robustness_computed_pair
# is a VALIDATION_CORRELATION_PAIRS key, or None if no alternate-instrument
# check applies to that claim.
PUBLISHED_VALIDATION_FIGURES = [
    {
        "comparison_id": "grayscale_nasdaq",
        "metric_label": "BTC-Nasdaq 90-day Pearson correlation",
        "publisher": "Grayscale Research (via Bloomingbit)",
        "published_value": 0.33,
        "published_as_of_date": "2026-09-02",
        "primary_computed_pair": "BTC_NASDAQ",
        "robustness_computed_pair": None,
        "explanation_key": "nasdaq_index_and_vendor_ambiguity",
    },
    {
        "comparison_id": "grayscale_gold",
        "metric_label": "BTC-gold 90-day Pearson correlation",
        "publisher": "Grayscale Research (via Bloomingbit)",
        "published_value": 0.50,
        "published_as_of_date": "2026-09-02",
        "primary_computed_pair": "BTC_GOLD",
        "robustness_computed_pair": None,
        "explanation_key": "gold_vendor_and_window_ambiguity",
    },
    {
        "comparison_id": "bitwise_gold",
        "metric_label": "BTC-gold 90-day Pearson correlation (six-year high)",
        "publisher": "Bitwise (via The Block / 24-7 Wall St.)",
        "published_value": 0.50,
        "published_as_of_date": "2026-08-31",
        "primary_computed_pair": "BTC_GOLD",
        "robustness_computed_pair": "BTC_GOLD_GCF",
        "explanation_key": "gold_etf_vs_futures",
    },
    {
        "comparison_id": "bitwise_nasdaq",
        "metric_label": "BTC-Nasdaq-100 90-day Pearson correlation (one-year low)",
        "publisher": "Bitwise (via The Block / 24-7 Wall St.)",
        "published_value": 0.30,
        "published_as_of_date": "2026-08-31",
        "primary_computed_pair": "BTC_NASDAQ",
        "robustness_computed_pair": "BTC_NASDAQ_NDX",
        "explanation_key": "nasdaq_composite_vs_100",
    },
]

VALIDATION_COMPARISON_TABLE_PATH = OUTPUTS_TABLES_DIR / "validation_comparison.csv"

# --- Sentiment analysis (BUILD-SPEC section 6.6, section 12 Phase 7) ---
# Forward-return horizons, in trading days, per section 6.6.
FORWARD_RETURN_HORIZONS_DAYS = [1, 5, 20, 60]

# Extreme-sentiment thresholds per section 6.6 ("value <= 20 extreme fear,
# >= 80 extreme greed, the index publisher's conventional bands"). NOTE:
# alternative.me's own fng_label field (already in the panel) uses
# different boundaries -- its "Extreme Fear" runs up to value 25, not 20 --
# so this module classifies buckets directly from fng_value against these
# two thresholds rather than reusing fng_label. See docs/decisions-log.md.
SENTIMENT_EXTREME_FEAR_MAX = 20
SENTIMENT_EXTREME_GREED_MIN = 80

SENTIMENT_BUCKET_EXTREME_FEAR = "EXTREME_FEAR"
SENTIMENT_BUCKET_EXTREME_GREED = "EXTREME_GREED"
SENTIMENT_BUCKET_MODERATE = "MODERATE"

SENTIMENT_FORWARD_RETURNS_DAILY_TABLE_PATH = OUTPUTS_TABLES_DIR / "sentiment_forward_returns_daily.csv"
SENTIMENT_FORWARD_RETURNS_SUMMARY_TABLE_PATH = OUTPUTS_TABLES_DIR / "sentiment_forward_returns_summary.csv"
SENTIMENT_TRANSITION_PROXIMITY_TABLE_PATH = OUTPUTS_TABLES_DIR / "sentiment_transition_proximity.csv"

# --- ML classifier (BUILD-SPEC section 6.7, section 12 Phase 8) ---
# Predict the regime label this many trading days ahead of the prediction
# date -- the only target this phase is allowed to build, per section 6.7.
ML_TARGET_HORIZON_DAYS = 5

# Correlation features use the same method (Pearson) the regime rule
# itself is classified from (src/regimes.py), not Spearman -- a feature
# should describe the same thing the target was built out of.
ML_CORRELATION_METHOD = "pearson"

# All window lengths below are trailing (backward-looking) only, per
# section 6.7's no-look-ahead, no-centered-window requirement -- every one
# of them is implemented as a rolling/.diff() calculation over the past N
# trading days ending on the prediction date, never a centered window.
ML_VOLATILITY_WINDOW_DAYS = 20
ML_MOMENTUM_WINDOW_DAYS = 20
ML_DXY_CHANGE_WINDOW_DAYS = 20
ML_REAL_YIELD_CHANGE_WINDOW_DAYS = 20
ML_SENTIMENT_CHANGE_WINDOW_DAYS = 14

# The DXY feature reads the same instrument (yfinance DX-Y.NYB) already
# used for the BTC_DXY correlation pair in CORRELATION_PAIRS above, rather
# than the FRED broad-dollar series (DTWEXBGS) -- one DXY reading used
# consistently by both the correlation and the change feature. See
# docs/decisions-log.md.
ML_DXY_FEATURE_COLUMN = "close_DX-Y.NYB"
# The 10-year real yield, per section 6.7's feature list.
ML_REAL_YIELD_COLUMN = "value_DFII10"

# Fixed class order used everywhere a model, table, or figure needs one:
# training, confusion matrices, and class-support all iterate labels in
# this order so every output lines up the same way. Matches
# charts.REGIME_LEGEND_ORDER.
ML_REGIME_LABEL_ORDER = [
    REGIME_LABEL_RISK_ASSET,
    REGIME_LABEL_HARD_ASSET,
    REGIME_LABEL_IDIOSYNCRATIC,
    REGIME_LABEL_MIXED,
]

# Walk-forward validation (section 6.7: TimeSeriesSplit or an explicit
# expanding window, never a random shuffled split -- see
# docs/decisions-log.md for why shuffling would be invalid here).
ML_TIMESERIES_N_SPLITS = 5
# Gap, in trading days, left empty between each fold's training data and
# its test data. Set equal to ML_TARGET_HORIZON_DAYS so that no training
# row's target (which is dated up to ML_TARGET_HORIZON_DAYS ahead of that
# row's own features) reaches forward into the following test fold's
# dates -- without this gap, the last few rows of every training fold
# would carry a target label dated inside the test fold.
ML_TIMESERIES_GAP_DAYS = ML_TARGET_HORIZON_DAYS

# Decision tree depth, fixed within section 6.7's allowed 3-5 range and
# picked before looking at any test-set result -- searching this value
# against test performance would itself be the kind of tuning-to-beat-
# baseline section 6.7 explicitly forbids. See docs/decisions-log.md.
ML_TREE_MAX_DEPTH = 4
ML_LOGISTIC_MAX_ITER = 1000
# Fixes scikit-learn's internal tie-breaking (e.g. which of two equally
# good tree splits is chosen) so the pipeline is reproducible run to run.
ML_RANDOM_STATE = 42

ML_FEATURES_TABLE_PATH = OUTPUTS_TABLES_DIR / "ml_features_daily.csv"
ML_MODEL_COMPARISON_TABLE_PATH = OUTPUTS_TABLES_DIR / "ml_model_comparison.csv"
ML_PER_FOLD_METRICS_TABLE_PATH = OUTPUTS_TABLES_DIR / "ml_per_fold_metrics.csv"
ML_CONFUSION_MATRICES_TABLE_PATH = OUTPUTS_TABLES_DIR / "ml_confusion_matrices.csv"
ML_CLASS_SUPPORT_TABLE_PATH = OUTPUTS_TABLES_DIR / "ml_class_support.csv"
