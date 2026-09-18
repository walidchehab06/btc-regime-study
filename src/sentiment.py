"""
Forward-return calculations bucketed by Fear & Greed extremes, and the
sentiment x regime cross-tab, per BUILD-SPEC-bitcoin-regime-study.md
section 12 (Phase 7).

Why this file exists: section 6.6 asks how Bitcoin behaves in the days
after an extreme sentiment reading, reported honestly -- every mean comes
with a sample size and a standard deviation, and the forward windows at
20 and 60 trading days overlap heavily day to day, which inflates apparent
significance and is called out explicitly rather than glossed over.
"""

import sys

import numpy as np
import pandas as pd
import sqlite3

from src import config


def load_panel():
    """
    Load the primary daily panel built in Phase 2.

    Why it exists: every table in this module is derived from the same
    source, panel_daily.parquet (BTC log returns and Fear & Greed value),
    so this is the one place that reads it.

    Parameters:
        None.

    Returns:
        pandas.DataFrame indexed by date (datetime), as saved by
        src/build_panel.py.
    """
    panel = pd.read_parquet(config.PANEL_PATH)
    print(f"[sentiment] loaded {config.PANEL_PATH}: {len(panel)} rows, {len(panel.columns)} columns")
    return panel


def assign_sentiment_bucket(fng_value):
    """
    Classify each day's Fear & Greed value into EXTREME_FEAR, EXTREME_GREED,
    or MODERATE, per BUILD-SPEC section 6.6's explicit thresholds.

    Why it exists: alternative.me's own fng_label field (already in the
    panel) uses different boundaries -- its "Extreme Fear" band runs up to
    value 25, not 20 -- so this project's bucketing is computed directly
    from fng_value against config.SENTIMENT_EXTREME_FEAR_MAX /
    SENTIMENT_EXTREME_GREED_MIN rather than reusing fng_label. See
    docs/decisions-log.md.

    Parameters:
        fng_value: pandas.Series, the Fear & Greed index value (0-100),
            indexed by date.

    Returns:
        pandas.Series of str (object dtype), same index as fng_value, one
        of config.SENTIMENT_BUCKET_EXTREME_FEAR, _EXTREME_GREED,
        _MODERATE, or None where fng_value is NaN.
    """
    bucket = pd.Series(config.SENTIMENT_BUCKET_MODERATE, index=fng_value.index, dtype=object)
    bucket[fng_value <= config.SENTIMENT_EXTREME_FEAR_MAX] = config.SENTIMENT_BUCKET_EXTREME_FEAR
    bucket[fng_value >= config.SENTIMENT_EXTREME_GREED_MIN] = config.SENTIMENT_BUCKET_EXTREME_GREED
    bucket[fng_value.isna()] = None
    return bucket


def compute_forward_log_returns(log_returns, horizon_days):
    """
    Compute, for every day, the sum of BTC's log returns over the next
    horizon_days trading days (day t+1 through day t+horizon_days).

    Why it exists: BUILD-SPEC section 6.6's forward-return calculation --
    the same forward window sql/analysis_queries.sql query 3 uses (ROWS
    BETWEEN 1 FOLLOWING AND horizon_days FOLLOWING), computed here in
    pandas because this module also needs the median across the full
    distribution, and SQLite has no built-in median function.

    Parameters:
        log_returns: pandas.Series indexed by date (chronological), daily
            log returns.
        horizon_days: int, e.g. one entry of
            config.FORWARD_RETURN_HORIZONS_DAYS.

    Returns:
        pandas.Series of float, same index as log_returns. Log returns add
        up over time, so the sum from day t+1 to day t+horizon_days is
        just the cumulative log return through day t+horizon_days minus
        the cumulative log return through day t -- NaN for the final
        horizon_days rows, which don't have a full forward window.
    """
    cumulative_log_return = log_returns.cumsum()
    forward_log_return = cumulative_log_return.shift(-horizon_days) - cumulative_log_return
    return forward_log_return


def build_forward_returns_long(panel):
    """
    Build the long-form table of forward BTC log returns, one row per
    (date, horizon) with a full forward window, with that day's sentiment
    bucket attached.

    Why it exists: figure 7's box plots need the full distribution of
    forward returns per bucket, not just the summary statistics --
    build_forward_returns_summary() aggregates this table, and
    charts.plot_forward_return_distributions_by_bucket() plots it
    directly.

    Parameters:
        panel: pandas.DataFrame, the primary daily panel, indexed by date,
            columns "log_return_BTC-USD" and "fng_value".

    Returns:
        pandas.DataFrame with columns date ('YYYY-MM-DD' text),
        horizon_days, sentiment_bucket, fng_value, forward_log_return.
        Also written to config.SENTIMENT_FORWARD_RETURNS_DAILY_TABLE_PATH.
    """
    btc_log_returns = panel["log_return_BTC-USD"]
    sentiment_bucket = assign_sentiment_bucket(panel["fng_value"])

    horizon_frames = []
    for horizon_days in config.FORWARD_RETURN_HORIZONS_DAYS:
        forward_log_return = compute_forward_log_returns(btc_log_returns, horizon_days)
        horizon_df = pd.DataFrame(
            {
                "date": panel.index,
                "horizon_days": horizon_days,
                "sentiment_bucket": sentiment_bucket.values,
                "fng_value": panel["fng_value"].values,
                "forward_log_return": forward_log_return.values,
            }
        )
        n_before = len(horizon_df)
        horizon_df = horizon_df.dropna(subset=["sentiment_bucket", "forward_log_return"])
        print(
            f"[sentiment] horizon={horizon_days}d: {n_before} days -> {len(horizon_df)} "
            "with both a sentiment reading and a full forward window"
        )
        horizon_frames.append(horizon_df)

    long_df = pd.concat(horizon_frames, ignore_index=True)
    long_df["date"] = long_df["date"].dt.strftime("%Y-%m-%d")

    config.OUTPUTS_TABLES_DIR.mkdir(parents=True, exist_ok=True)
    long_df.to_csv(config.SENTIMENT_FORWARD_RETURNS_DAILY_TABLE_PATH, index=False)
    print(f"[sentiment] wrote {len(long_df)} rows -> {config.SENTIMENT_FORWARD_RETURNS_DAILY_TABLE_PATH}")
    return long_df


def build_forward_returns_summary(long_df):
    """
    Aggregate the long-form forward-return table into n, mean, median, and
    standard deviation per (horizon, sentiment bucket).

    Why it exists: BUILD-SPEC section 6.6's mandatory reporting
    requirement -- "a mean forward return quoted without n and standard
    deviation is not a result, it is a talking point." Uses the population
    standard deviation (ddof=0), matching the convention already used in
    src/core_math.py:annualized_volatility() and the
    AVG(x^2)-AVG(x)^2 formula in sql/analysis_queries.sql, rather than the
    n-1 sample correction.

    Parameters:
        long_df: pandas.DataFrame from build_forward_returns_long().

    Returns:
        pandas.DataFrame, one row per (horizon_days, sentiment_bucket),
        columns n, mean_forward_log_return, median_forward_log_return,
        std_forward_log_return. Also written to
        config.SENTIMENT_FORWARD_RETURNS_SUMMARY_TABLE_PATH.
    """
    grouped = long_df.groupby(["horizon_days", "sentiment_bucket"])["forward_log_return"]
    summary_df = grouped.agg(
        n="count",
        mean_forward_log_return="mean",
        median_forward_log_return="median",
        std_forward_log_return=lambda values: float(np.std(values, ddof=0)),
    ).reset_index()

    config.OUTPUTS_TABLES_DIR.mkdir(parents=True, exist_ok=True)
    summary_df.to_csv(config.SENTIMENT_FORWARD_RETURNS_SUMMARY_TABLE_PATH, index=False)
    print(f"[sentiment] wrote {len(summary_df)} rows -> {config.SENTIMENT_FORWARD_RETURNS_SUMMARY_TABLE_PATH}")
    return summary_df


def compute_days_to_nearest_transition(regimes_daily_df):
    """
    For every day, how many trading days separate it from the nearest
    boundary (start or end) of the regime period it falls inside.

    Why it exists: the concrete version of BUILD-SPEC section 6.6's "ask
    whether extremes cluster near transitions" -- a day right at a regime
    boundary has distance 0; a day in the middle of a long, stable regime
    has a large distance.

    Parameters:
        regimes_daily_df: pandas.DataFrame with columns date ('YYYY-MM-DD'
            text, chronological) and regime_id, e.g. the SQLite 'regimes'
            table (src/regimes.py:build_regimes_daily()).

    Returns:
        pandas.DataFrame with columns date, days_to_nearest_transition
        (int, trading days -- 0 on the first or last day of a regime
        period).
    """
    df = regimes_daily_df.sort_values("date").reset_index(drop=True)
    # cumcount() numbers each row's position within its regime_id group,
    # from the front (days since the period started) or the back (days
    # until it ends); the smaller of the two is the distance to whichever
    # boundary is nearer.
    days_since_start = df.groupby("regime_id").cumcount()
    days_until_end = df.groupby("regime_id").cumcount(ascending=False)
    df["days_to_nearest_transition"] = np.minimum(days_since_start, days_until_end)
    return df[["date", "days_to_nearest_transition"]]


def build_transition_proximity_summary(panel, regimes_daily_df):
    """
    Compare how close extreme-sentiment days sit to a regime transition
    against how close moderate-sentiment days sit, as n/mean/median of
    trading-day distance -- no significance test, descriptive only.

    Why it exists: the quantitative half of BUILD-SPEC section 6.6's "ask
    whether extremes cluster near transitions," alongside the SQL
    cross-tab (query 10 in sql/analysis_queries.sql), which counts days
    per bucket per regime but doesn't say anything about where within a
    regime those days fall.

    Parameters:
        panel: pandas.DataFrame, the primary daily panel, indexed by date,
            column "fng_value".
        regimes_daily_df: pandas.DataFrame with columns date, regime_label,
            regime_id, e.g. the SQLite 'regimes' table.

    Returns:
        pandas.DataFrame with columns sentiment_bucket, n,
        mean_days_to_nearest_transition, median_days_to_nearest_transition.
        Also written to config.SENTIMENT_TRANSITION_PROXIMITY_TABLE_PATH.
    """
    proximity_df = compute_days_to_nearest_transition(regimes_daily_df)
    proximity_df["date"] = pd.to_datetime(proximity_df["date"])
    proximity_df = proximity_df.set_index("date")

    sentiment_bucket = assign_sentiment_bucket(panel["fng_value"]).rename("sentiment_bucket")

    print(
        f"[sentiment] transition proximity merge: {len(proximity_df)} regime-labeled days, "
        f"{len(sentiment_bucket.dropna())} days with a sentiment reading"
    )
    combined = proximity_df.join(sentiment_bucket, how="inner").dropna(subset=["sentiment_bucket"])
    print(f"[sentiment] transition proximity merge: {len(combined)} days with both")

    grouped = combined.groupby("sentiment_bucket")["days_to_nearest_transition"]
    summary_df = grouped.agg(n="count", mean_days_to_nearest_transition="mean", median_days_to_nearest_transition="median").reset_index()

    config.OUTPUTS_TABLES_DIR.mkdir(parents=True, exist_ok=True)
    summary_df.to_csv(config.SENTIMENT_TRANSITION_PROXIMITY_TABLE_PATH, index=False)
    print(f"[sentiment] wrote {len(summary_df)} rows -> {config.SENTIMENT_TRANSITION_PROXIMITY_TABLE_PATH}")
    return summary_df


def main():
    """
    Run the Phase 7 sentiment analysis: forward returns bucketed by Fear &
    Greed extremes, with n/mean/median/std at every horizon, and the
    transition-proximity check for whether extreme sentiment clusters near
    regime boundaries.

    Why it exists: this is the entry point src/run_all.py calls for Phase
    7 (BUILD-SPEC section 12). Opens its own connection to config.DB_PATH
    to read the regimes table Phase 5 already loaded. The sentiment x
    regime cross-tab itself (counts only, no median needed) is computed in
    SQL instead -- query 10 in sql/analysis_queries.sql, run later by
    src/run_all.py:run_analysis_queries() -- only the statistics that need
    a median run here in pandas, since SQLite has no built-in median
    function. See docs/decisions-log.md.

    Parameters:
        None.

    Returns:
        None.
    """
    panel = load_panel()

    long_df = build_forward_returns_long(panel)
    build_forward_returns_summary(long_df)

    conn = sqlite3.connect(config.DB_PATH)
    try:
        regimes_daily_df = pd.read_sql_query("SELECT date, regime_label, regime_id FROM regimes ORDER BY date", conn)
        print(f"[sentiment] loaded {len(regimes_daily_df)} rows from regimes")
    finally:
        conn.close()

    build_transition_proximity_summary(panel, regimes_daily_df)


if __name__ == "__main__":
    main()
    sys.exit(0)
