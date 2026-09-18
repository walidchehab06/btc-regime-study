-- Analysis queries for data/processed/btc_regime.db.
-- Per BUILD-SPEC-bitcoin-regime-study.md section 8. Each query is preceded
-- by a comment stating the question in English. src/database.py runs each
-- one and writes its result to outputs/tables/ as a CSV.
--
-- Queries 4 and 6 depend on regimes/regime_periods, empty until Phase 5,
-- and will return 0 rows honestly until then. See docs/decisions-log.md.

-- Query 1: By calendar year, what was the average 90-day BTC-Nasdaq
-- correlation and the average 90-day BTC-gold correlation?
SELECT
    CAST(strftime('%Y', date) AS INTEGER) AS calendar_year,
    pair,
    AVG(correlation) AS avg_correlation,
    COUNT(*) AS n_days
FROM rolling_correlations
WHERE window = 90
  AND method = 'pearson'
  AND pair IN ('BTC_NASDAQ', 'BTC_GOLD')
GROUP BY calendar_year, pair
ORDER BY calendar_year, pair;

-- Query 2: What are the 20 single days on which the 90-day BTC-gold
-- correlation moved the most from the previous day, and what was the
-- Fear & Greed reading on each of those days?
WITH btc_gold_90d AS (
    SELECT date, correlation
    FROM rolling_correlations
    WHERE pair = 'BTC_GOLD' AND window = 90 AND method = 'pearson'
),
daily_change AS (
    SELECT
        date,
        correlation - LAG(correlation) OVER (ORDER BY date) AS correlation_change
    FROM btc_gold_90d
)
SELECT
    c.date,
    c.correlation_change,
    s.fng_value,
    s.fng_label
FROM daily_change c
JOIN sentiment_daily s ON s.date = c.date
WHERE c.correlation_change IS NOT NULL
ORDER BY ABS(c.correlation_change) DESC
LIMIT 20;

-- Query 3: Grouped by Fear & Greed bucket (the label the API itself
-- assigns -- Extreme Fear, Fear, Neutral, Greed, Extreme Greed), what is
-- Bitcoin's average forward 20-trading-day return, with how many days
-- fall in each bucket and how dispersed the returns are?
WITH btc_returns AS (
    SELECT date, log_return
    FROM returns_daily
    WHERE ticker = 'BTC-USD'
),
btc_with_forward_return AS (
    SELECT
        date,
        SUM(log_return) OVER (
            ORDER BY date
            ROWS BETWEEN 1 FOLLOWING AND 20 FOLLOWING
        ) AS forward_20d_log_return,
        COUNT(log_return) OVER (
            ORDER BY date
            ROWS BETWEEN 1 FOLLOWING AND 20 FOLLOWING
        ) AS forward_days_available
    FROM btc_returns
)
SELECT
    s.fng_label AS sentiment_bucket,
    COUNT(*) AS n_days,
    AVG(f.forward_20d_log_return) AS avg_forward_20d_log_return,
    -- SQLite has no built-in STDDEV; variance = E[x^2] - (E[x])^2.
    SQRT(
        AVG(f.forward_20d_log_return * f.forward_20d_log_return)
        - AVG(f.forward_20d_log_return) * AVG(f.forward_20d_log_return)
    ) AS stddev_forward_20d_log_return
FROM btc_with_forward_return f
JOIN sentiment_daily s ON s.date = f.date
WHERE f.forward_days_available = 20
GROUP BY s.fng_label
ORDER BY n_days DESC;

-- Query 4: For each regime type, how many separate periods occurred, and
-- what was their total and average duration in trading days, ordered
-- from longest total duration to shortest?
SELECT
    regime_label,
    COUNT(*) AS n_periods,
    SUM(n_days) AS total_days,
    AVG(n_days) AS avg_period_length_days
FROM regime_periods
GROUP BY regime_label
ORDER BY total_days DESC;

-- Query 5: On which days did the BTC-Nasdaq 90-day correlation and the
-- BTC-gold 90-day correlation cross over -- the one that was larger on
-- the previous day is no longer the larger one -- listed chronologically?
WITH nasdaq_90d AS (
    SELECT date, correlation AS corr_nasdaq
    FROM rolling_correlations
    WHERE pair = 'BTC_NASDAQ' AND window = 90 AND method = 'pearson'
),
gold_90d AS (
    SELECT date, correlation AS corr_gold
    FROM rolling_correlations
    WHERE pair = 'BTC_GOLD' AND window = 90 AND method = 'pearson'
),
combined AS (
    SELECT
        n.date,
        n.corr_nasdaq,
        g.corr_gold,
        CASE WHEN n.corr_nasdaq > g.corr_gold THEN 'NASDAQ_LEADS' ELSE 'GOLD_LEADS' END AS leader
    FROM nasdaq_90d n
    JOIN gold_90d g ON g.date = n.date
),
with_previous_leader AS (
    SELECT
        date,
        corr_nasdaq,
        corr_gold,
        leader,
        LAG(leader) OVER (ORDER BY date) AS previous_leader
    FROM combined
)
SELECT date, corr_nasdaq, corr_gold, previous_leader, leader
FROM with_previous_leader
WHERE previous_leader IS NOT NULL AND leader != previous_leader
ORDER BY date;

-- Query 6: For each regime type, what was Bitcoin's annualized volatility
-- (standard deviation of daily log returns, scaled by the square root of
-- 252 trading days), computed directly in SQL?
WITH btc_returns AS (
    SELECT date, log_return
    FROM returns_daily
    WHERE ticker = 'BTC-USD'
),
btc_with_regime AS (
    SELECT r.date, r.log_return, g.regime_label
    FROM btc_returns r
    JOIN regimes g ON g.date = r.date
)
SELECT
    regime_label,
    COUNT(*) AS n_days,
    SQRT(
        AVG(log_return * log_return) - AVG(log_return) * AVG(log_return)
    ) * SQRT(252.0) AS annualized_volatility
FROM btc_with_regime
GROUP BY regime_label
ORDER BY annualized_volatility DESC;

-- Query 7: Reconciliation check. Does the log return stored in
-- returns_daily (built by melting the wide panel with pandas) match the
-- log return recomputed independently, row by row, straight from
-- panel_daily.parquet's close prices? This is the Phase 3 reconciliation:
-- it proves the ETL load did not silently change a value. src/database.py
-- asserts this query returns zero rows after every load. (The
-- correlation-value reconciliation the spec describes for this slot is
-- added once Phase 4 populates rolling_correlations -- see
-- docs/decisions-log.md.)
SELECT
    a.date,
    a.ticker,
    a.log_return AS log_return_from_etl_load,
    b.log_return AS log_return_recomputed_independently,
    ABS(a.log_return - b.log_return) AS abs_difference
FROM returns_daily a
JOIN returns_daily_recomputed_check b
    ON a.date = b.date AND a.ticker = b.ticker
WHERE ABS(a.log_return - b.log_return) > 0.000000001
ORDER BY abs_difference DESC;

-- Query 8: Reconciliation check. Does the 90-day Pearson correlation
-- stored in rolling_correlations (computed with pandas .rolling().corr())
-- match the same correlation recomputed independently with
-- src/core_math.py's hand-written NumPy function? This is the BUILD-SPEC
-- section 6.3 check src/correlations.py already asserts in-memory before
-- loading either table; this query re-proves it at the SQL level, the
-- literal "join proving that the correlation values stored in SQLite
-- match those computed in Pandas" BUILD-SPEC section 8 describes.
-- src/database.py asserts this query returns zero rows after every load.
SELECT
    a.date,
    a.pair,
    a.correlation AS correlation_pandas,
    b.correlation AS correlation_hand_written,
    ABS(a.correlation - b.correlation) AS abs_difference
FROM rolling_correlations a
JOIN rolling_correlations_recomputed_check b
    ON a.date = b.date AND a.pair = b.pair AND a.window = b.window AND a.method = b.method
WHERE a.window = 90
  AND a.method = 'pearson'
  AND ABS(a.correlation - b.correlation) > 0.000000001
ORDER BY abs_difference DESC;

-- Query 9: The regime timeline -- every regime period, in order, with its
-- start date, end date, and duration in trading days. This is the literal
-- "regime timeline table" BUILD-SPEC section 6.4 asks for; query 4
-- aggregates the same table by regime_label instead of listing periods.
SELECT
    regime_id,
    regime_label,
    start_date,
    end_date,
    n_days
FROM regime_periods
ORDER BY start_date;

-- Query 10: Cross-tabulated against regime label, how many days fall into
-- each sentiment bucket -- extreme fear (Fear & Greed value <= 20),
-- extreme greed (>= 80), or moderate (everything else)? Per BUILD-SPEC
-- section 6.6's mandatory sentiment x regime cross-tab. Bucket boundaries
-- match config.SENTIMENT_EXTREME_FEAR_MAX / SENTIMENT_EXTREME_GREED_MIN --
-- computed directly from fng_value here rather than reusing
-- sentiment_daily.fng_label, whose own "Extreme Fear" band uses a
-- different cutoff (<= 25, not <= 20). See docs/decisions-log.md.
SELECT
    CASE
        WHEN s.fng_value <= 20 THEN 'EXTREME_FEAR'
        WHEN s.fng_value >= 80 THEN 'EXTREME_GREED'
        ELSE 'MODERATE'
    END AS sentiment_bucket,
    g.regime_label,
    COUNT(*) AS n_days
FROM sentiment_daily s
JOIN regimes g ON g.date = s.date
GROUP BY sentiment_bucket, g.regime_label
ORDER BY sentiment_bucket, g.regime_label;
