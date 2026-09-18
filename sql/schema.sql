-- Schema for data/processed/btc_regime.db.
-- Per BUILD-SPEC-bitcoin-regime-study.md section 8: long-format tables so
-- SQL can join and aggregate directly, rather than storing the wide
-- pandas panel as-is. Every table is indexed on date, per section 8.
--
-- rolling_correlations, regimes, and regime_periods are created here with
-- their final structure but stay empty until Phase 4 (correlations) and
-- Phase 5 (regime classification) run and populate them. See
-- docs/decisions-log.md for the reasoning.

CREATE TABLE IF NOT EXISTS prices_daily (
    date TEXT NOT NULL,
    ticker TEXT NOT NULL,
    close REAL,
    volume REAL,
    PRIMARY KEY (date, ticker)
);
CREATE INDEX IF NOT EXISTS idx_prices_daily_date ON prices_daily(date);

CREATE TABLE IF NOT EXISTS returns_daily (
    date TEXT NOT NULL,
    ticker TEXT NOT NULL,
    log_return REAL,
    PRIMARY KEY (date, ticker)
);
CREATE INDEX IF NOT EXISTS idx_returns_daily_date ON returns_daily(date);

-- is_forward_filled is stored as an INTEGER (0/1), SQLite's boolean
-- convention, per section 8's note that the flag matters for honesty:
-- it marks a value carried forward from a monthly/weekly FRED release
-- rather than an observation published that day.
CREATE TABLE IF NOT EXISTS macro_daily (
    date TEXT NOT NULL,
    series_id TEXT NOT NULL,
    value REAL,
    is_forward_filled INTEGER NOT NULL,
    PRIMARY KEY (date, series_id)
);
CREATE INDEX IF NOT EXISTS idx_macro_daily_date ON macro_daily(date);

CREATE TABLE IF NOT EXISTS sentiment_daily (
    date TEXT NOT NULL PRIMARY KEY,
    fng_value REAL,
    fng_label TEXT
);
CREATE INDEX IF NOT EXISTS idx_sentiment_daily_date ON sentiment_daily(date);

-- pair is a string like 'BTC_NASDAQ' or 'BTC_GOLD'; window is 30 or 90
-- (trading days); method is 'pearson' or 'spearman'. Populated in Phase 4.
CREATE TABLE IF NOT EXISTS rolling_correlations (
    date TEXT NOT NULL,
    pair TEXT NOT NULL,
    window INTEGER NOT NULL,
    method TEXT NOT NULL,
    correlation REAL,
    PRIMARY KEY (date, pair, window, method)
);
CREATE INDEX IF NOT EXISTS idx_rolling_correlations_date ON rolling_correlations(date);

-- regime_id links a single day (in regimes) to the regime_periods row it
-- falls inside. Populated in Phase 5, after the persistence filter runs.
CREATE TABLE IF NOT EXISTS regimes (
    date TEXT NOT NULL PRIMARY KEY,
    regime_label TEXT NOT NULL,
    regime_id INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_regimes_date ON regimes(date);

-- No single "date" column exists on this table by definition (each row
-- spans a period), so start_date is indexed to satisfy section 8's
-- "index on date for every table" in the closest applicable sense.
CREATE TABLE IF NOT EXISTS regime_periods (
    regime_id INTEGER NOT NULL PRIMARY KEY,
    regime_label TEXT NOT NULL,
    start_date TEXT NOT NULL,
    end_date TEXT NOT NULL,
    n_days INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_regime_periods_start_date ON regime_periods(start_date);

-- Staging table for the Phase 3 reconciliation check (analysis query 7).
-- Holds BTC-USD's log return recomputed independently, row by row, from
-- panel_daily.parquet's close prices -- a separate code path from the
-- vectorized melt that builds returns_daily, so a bug in one is unlikely
-- to be replicated identically in the other. See docs/decisions-log.md.
CREATE TABLE IF NOT EXISTS returns_daily_recomputed_check (
    date TEXT NOT NULL,
    ticker TEXT NOT NULL,
    log_return REAL,
    PRIMARY KEY (date, ticker)
);
CREATE INDEX IF NOT EXISTS idx_returns_daily_recomputed_check_date ON returns_daily_recomputed_check(date);

-- Staging table for the Phase 4 reconciliation check (analysis query 8).
-- Holds the 90-day Pearson BTC correlations recomputed independently with
-- src/core_math.py's hand-written NumPy function, per BUILD-SPEC section
-- 6.3 -- a separate code path from the pandas .rolling().corr() values
-- stored in rolling_correlations. See docs/decisions-log.md.
CREATE TABLE IF NOT EXISTS rolling_correlations_recomputed_check (
    date TEXT NOT NULL,
    pair TEXT NOT NULL,
    window INTEGER NOT NULL,
    method TEXT NOT NULL,
    correlation REAL,
    PRIMARY KEY (date, pair, window, method)
);
CREATE INDEX IF NOT EXISTS idx_rolling_correlations_recomputed_check_date ON rolling_correlations_recomputed_check(date);

-- Phase 6 (validation) alternate-instrument correlations: BTC vs Nasdaq-100
-- and BTC vs gold futures (GC=F), used only to compare against published
-- institutional figures in docs/validation.md. Kept as its own table,
-- separate from rolling_correlations, because
-- database.load_dataframe_to_table()'s row-count assertion only holds for
-- a table that is empty before the insert -- rolling_correlations is
-- already populated by Phase 4 by the time Phase 6 runs. See
-- docs/decisions-log.md.
CREATE TABLE IF NOT EXISTS rolling_correlations_validation (
    date TEXT NOT NULL,
    pair TEXT NOT NULL,
    window INTEGER NOT NULL,
    method TEXT NOT NULL,
    correlation REAL,
    PRIMARY KEY (date, pair, window, method)
);
CREATE INDEX IF NOT EXISTS idx_rolling_correlations_validation_date ON rolling_correlations_validation(date);
