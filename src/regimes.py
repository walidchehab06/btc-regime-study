"""
Regime classification, persistence filter, and sensitivity grid, per
BUILD-SPEC-bitcoin-regime-study.md section 12 (Phase 5).

Why this file exists: this is where section 6.4's rule-based regime
labels get computed from the 90-day Pearson correlations Phase 4 already
loaded, where the persistence filter turns noisy daily labels into a
handful of multi-month regime periods, and where section 6.5's mandatory
sensitivity grid is run.
"""

import sys

import numpy as np
import pandas as pd
import sqlite3

from src import charts, config, core_math, database


def load_panel():
    """
    Load the primary daily panel built in Phase 2.

    Why it exists: per-regime statistics (annualized return, volatility,
    max drawdown, average Fear & Greed level) are read straight from the
    panel, same source as every other phase.

    Parameters:
        None.

    Returns:
        pandas.DataFrame indexed by date (datetime), as saved by
        src/build_panel.py.
    """
    panel = pd.read_parquet(config.PANEL_PATH)
    print(f"[regimes] loaded {config.PANEL_PATH}: {len(panel)} rows, {len(panel.columns)} columns")
    return panel


def load_correlations_wide(conn):
    """
    Load the 90-day Pearson BTC_NASDAQ and BTC_GOLD correlations into a
    wide DataFrame, one column per pair.

    Why it exists: BUILD-SPEC section 6.4's regime rule is evaluated
    jointly on both pairs' correlations for the same date, which needs
    them side by side rather than in rolling_correlations' long format.

    Parameters:
        conn: sqlite3.Connection, open connection to btc_regime.db.

    Returns:
        pandas.DataFrame indexed by date (datetime), columns
        'BTC_NASDAQ' and 'BTC_GOLD', only dates where both are present.
    """
    pairs = ["BTC_NASDAQ", "BTC_GOLD"]
    placeholders = ",".join("?" for _ in pairs)
    query = (
        "SELECT date, pair, correlation FROM rolling_correlations "
        f"WHERE window = ? AND method = 'pearson' AND pair IN ({placeholders})"
    )
    long_df = pd.read_sql_query(query, conn, params=[config.CORRELATION_WINDOW_HEADLINE, *pairs])
    long_df["date"] = pd.to_datetime(long_df["date"])
    wide_df = long_df.pivot(index="date", columns="pair", values="correlation").sort_index()
    wide_df = wide_df.dropna()
    print(
        f"[regimes] loaded {len(long_df)} rolling_correlations rows -> "
        f"{len(wide_df)} dates with both BTC_NASDAQ and BTC_GOLD present"
    )
    return wide_df


def classify_regime(corr_nasdaq, corr_gold, nasdaq_threshold, gold_threshold, idio_threshold):
    """
    Apply the BUILD-SPEC section 6.4 rule-based regime definition to one
    day's pair of 90-day correlations.

    Why it exists: this is the classification rule itself, kept as a pure
    function of its thresholds (not read from config.py directly) so
    run_sensitivity_grid() can call it with different threshold values
    without any global state.

    Parameters:
        corr_nasdaq: float, that day's 90-day Pearson corr(BTC, Nasdaq).
        corr_gold: float, that day's 90-day Pearson corr(BTC, Gold).
        nasdaq_threshold: float, e.g. config.REGIME_NASDAQ_THRESHOLD.
        gold_threshold: float, e.g. config.REGIME_GOLD_THRESHOLD.
        idio_threshold: float, e.g. config.REGIME_IDIOSYNCRATIC_THRESHOLD.

    Returns:
        str, one of config.REGIME_LABEL_RISK_ASSET, _HARD_ASSET,
        _IDIOSYNCRATIC, or _MIXED.
    """
    if corr_nasdaq >= nasdaq_threshold and corr_nasdaq > corr_gold:
        return config.REGIME_LABEL_RISK_ASSET
    if corr_gold >= gold_threshold and corr_gold > corr_nasdaq:
        return config.REGIME_LABEL_HARD_ASSET
    if abs(corr_nasdaq) < idio_threshold and abs(corr_gold) < idio_threshold:
        return config.REGIME_LABEL_IDIOSYNCRATIC
    return config.REGIME_LABEL_MIXED


def classify_regime_series(correlations_wide, nasdaq_threshold, gold_threshold, idio_threshold):
    """
    Apply classify_regime() to every date in correlations_wide.

    Why it exists: the day-by-day version of classify_regime(), used both
    for the baseline classification and for every combination in the
    sensitivity grid.

    Parameters:
        correlations_wide: pandas.DataFrame indexed by date, columns
            'BTC_NASDAQ' and 'BTC_GOLD', from load_correlations_wide().
        nasdaq_threshold: float.
        gold_threshold: float.
        idio_threshold: float.

    Returns:
        pandas.Series of str, indexed like correlations_wide.
    """
    return correlations_wide.apply(
        lambda row: classify_regime(
            row["BTC_NASDAQ"], row["BTC_GOLD"], nasdaq_threshold, gold_threshold, idio_threshold
        ),
        axis=1,
    )


def _runs_from_labels(labels):
    """
    Collapse a list of daily labels into consecutive-run form.

    Why it exists: shared by apply_persistence_filter(),
    build_regime_periods(), build_regimes_daily(), and the before/after
    stability summary, all of which work run by run rather than day by
    day.

    Parameters:
        labels: list of str, in chronological order.

    Returns:
        List of (label, length) tuples, one per maximal run of identical
        consecutive labels, in order.
    """
    runs = []
    current_label = None
    current_length = 0
    for label in labels:
        if label == current_label:
            current_length += 1
        else:
            if current_label is not None:
                runs.append((current_label, current_length))
            current_label = label
            current_length = 1
    if current_label is not None:
        runs.append((current_label, current_length))
    return runs


def _labels_from_runs(runs):
    """
    Expand (label, length) runs back into one label per day.

    Why it exists: the inverse of _runs_from_labels(), used to turn
    apply_persistence_filter()'s merged runs back into a day-by-day label
    list.

    Parameters:
        runs: list of (label, length) tuples.

    Returns:
        List of str, one entry per day.
    """
    labels = []
    for label, length in runs:
        labels.extend([label] * length)
    return labels


def apply_persistence_filter(labels, min_days):
    """
    Merge any run of consecutive identical labels shorter than min_days
    into its neighboring regime, per BUILD-SPEC section 6.4's persistence
    filter.

    Why it exists: the raw day-by-day regime labels flicker near every
    threshold crossing -- see docs/methodology.md's before/after
    comparison. This turns that noise into a handful of stable, multi-
    week regime periods.

    Merge direction: a short run is merged into the PRECEDING run's
    label -- a brief blip during an established regime doesn't rewrite
    the regime that came before it. The one exception is a short run at
    the very start of the series, which has no preceding run and instead
    borrows the label of the run that follows it. Merging can make a run
    long enough to then swallow its own next short neighbor, so this
    repeats until every remaining run is >= min_days (or only one run is
    left). See docs/decisions-log.md for why this direction was chosen.

    Parameters:
        labels: list of str, one per trading day, in chronological order
            (e.g. classify_regime_series() applied to every row of
            load_correlations_wide()).
        min_days: int, e.g. config.REGIME_PERSISTENCE_MIN_DAYS.

    Returns:
        List of str, same length as labels, with every short run
        relabelled.
    """
    runs = _runs_from_labels(labels)

    changed = True
    while changed:
        changed = False
        merged = []
        skip_next = False
        for i, (label, length) in enumerate(runs):
            if skip_next:
                skip_next = False
                continue
            if length < min_days and len(runs) > 1:
                if merged:
                    prev_label, prev_length = merged[-1]
                    merged[-1] = (prev_label, prev_length + length)
                else:
                    next_label, next_length = runs[i + 1]
                    merged.append((next_label, length + next_length))
                    skip_next = True
                changed = True
            else:
                merged.append((label, length))

        collapsed = []
        for label, length in merged:
            if collapsed and collapsed[-1][0] == label:
                collapsed[-1] = (label, collapsed[-1][1] + length)
                changed = True
            else:
                collapsed.append((label, length))
        runs = collapsed

    return _labels_from_runs(runs)


def build_regime_periods(dates, filtered_labels):
    """
    Collapse a filtered day-by-day label sequence into the regime_periods
    table shape: one row per period with its label, start date, end date,
    and length in trading days.

    Why it exists: this is the section 6.4 "regime timeline table"
    deliverable and what gets loaded into the regime_periods table
    (sql/schema.sql).

    Parameters:
        dates: pandas.DatetimeIndex, chronological, same length as
            filtered_labels.
        filtered_labels: list of str, same length as dates, from
            apply_persistence_filter().

    Returns:
        pandas.DataFrame with columns regime_id (1-based, in
        chronological order), regime_label, start_date, end_date (both
        'YYYY-MM-DD' text), n_days.
    """
    assert len(dates) == len(filtered_labels), "dates and filtered_labels must be the same length"

    runs = _runs_from_labels(filtered_labels)
    rows = []
    position = 0
    for regime_id, (label, length) in enumerate(runs, start=1):
        start_date = dates[position]
        end_date = dates[position + length - 1]
        rows.append(
            {
                "regime_id": regime_id,
                "regime_label": label,
                "start_date": pd.Timestamp(start_date).strftime("%Y-%m-%d"),
                "end_date": pd.Timestamp(end_date).strftime("%Y-%m-%d"),
                "n_days": length,
            }
        )
        position += length

    return pd.DataFrame(rows)


def build_regimes_daily(dates, filtered_labels):
    """
    Build the day-by-day regimes table: one row per date with its
    filtered regime_label and the regime_id of the period it falls
    inside.

    Why it exists: sql/schema.sql's regimes table is the per-day join key
    analysis queries 3 and 6 use to attach a regime label to every date;
    regime_periods alone only has period boundaries, not a row per date.

    Parameters:
        dates: pandas.DatetimeIndex, chronological, same length as
            filtered_labels.
        filtered_labels: list of str, same length as dates, from
            apply_persistence_filter().

    Returns:
        pandas.DataFrame with columns date ('YYYY-MM-DD' text),
        regime_label, regime_id -- regime_id numbered the same way
        build_regime_periods() numbers its regime_id column, since both
        are derived from the same run structure.
    """
    runs = _runs_from_labels(filtered_labels)
    regime_ids = []
    for regime_id, (_, length) in enumerate(runs, start=1):
        regime_ids.extend([regime_id] * length)

    return pd.DataFrame(
        {
            "date": [pd.Timestamp(d).strftime("%Y-%m-%d") for d in dates],
            "regime_label": filtered_labels,
            "regime_id": regime_ids,
        }
    )


def compute_regime_summary_statistics(regime_periods_df, panel):
    """
    Compute Bitcoin's annualized return, annualized volatility, maximum
    drawdown, and the average Fear & Greed level within each regime
    period.

    Why it exists: the BUILD-SPEC section 6.4 "per-regime statistics"
    deliverable. Written directly to outputs/tables/ rather than through
    sql/analysis_queries.sql, since it mixes price, return, and sentiment
    data with the hand-written stat functions in src/core_math.py -- a
    pandas computation, not a SQL join. See docs/decisions-log.md.

    Parameters:
        regime_periods_df: pandas.DataFrame from build_regime_periods().
        panel: pandas.DataFrame, the primary daily panel
            (panel_daily.parquet), indexed by date.

    Returns:
        pandas.DataFrame, one row per regime period, columns regime_id,
        regime_label, start_date, end_date, n_days,
        btc_annualized_return, btc_annualized_volatility,
        btc_max_drawdown, avg_fng_value. Also written to
        config.REGIME_SUMMARY_STATS_TABLE_PATH.
    """
    rows = []
    for _, period in regime_periods_df.iterrows():
        period_slice = panel.loc[period["start_date"] : period["end_date"]]
        btc_log_returns = period_slice["log_return_BTC-USD"].dropna()
        btc_close = period_slice["close_BTC-USD"].dropna()

        rows.append(
            {
                "regime_id": period["regime_id"],
                "regime_label": period["regime_label"],
                "start_date": period["start_date"],
                "end_date": period["end_date"],
                "n_days": period["n_days"],
                "btc_annualized_return": core_math.annualized_return(
                    btc_log_returns, config.TRADING_DAYS_PER_YEAR
                ),
                "btc_annualized_volatility": core_math.annualized_volatility(
                    btc_log_returns, config.TRADING_DAYS_PER_YEAR
                ),
                "btc_max_drawdown": core_math.max_drawdown(btc_close),
                "avg_fng_value": float(period_slice["fng_value"].mean()),
            }
        )

    summary_df = pd.DataFrame(rows)
    config.OUTPUTS_TABLES_DIR.mkdir(parents=True, exist_ok=True)
    summary_df.to_csv(config.REGIME_SUMMARY_STATS_TABLE_PATH, index=False)
    print(f"[regimes] wrote {len(summary_df)} rows -> {config.REGIME_SUMMARY_STATS_TABLE_PATH}")
    return summary_df


def run_sensitivity_grid(correlations_wide):
    """
    Re-run regime classification and the persistence filter across every
    combination of Nasdaq and gold thresholds in
    config.SENSITIVITY_NASDAQ_THRESHOLDS x
    config.SENSITIVITY_GOLD_THRESHOLDS, per BUILD-SPEC section 6.5's
    mandatory sensitivity analysis.

    Why it exists: section 6.5 requires showing whether the baseline
    regime rule's thresholds are load-bearing -- if a small change in
    either threshold produces a materially different set of regimes, the
    baseline result is fragile, and that has to be reported, not hidden.
    The idiosyncratic threshold and the persistence window are held fixed
    at their config.py values; section 6.5 only asks the Nasdaq and gold
    thresholds to vary.

    Parameters:
        correlations_wide: pandas.DataFrame indexed by date, columns
            'BTC_NASDAQ' and 'BTC_GOLD', from load_correlations_wide().

    Returns:
        pandas.DataFrame, one row per threshold combination, columns
        nasdaq_threshold, gold_threshold, n_regime_periods, one
        share_<LABEL> column per regime label (share of days), and
        shift_survives_2026 (bool: whether any regime transition -- a
        period's start_date, excluding the series' very first period --
        lands in calendar year 2026). Also written to
        config.SENSITIVITY_GRID_TABLE_PATH.
    """
    dates = correlations_wide.index
    rows = []

    for nasdaq_threshold in config.SENSITIVITY_NASDAQ_THRESHOLDS:
        for gold_threshold in config.SENSITIVITY_GOLD_THRESHOLDS:
            raw_labels = list(
                classify_regime_series(
                    correlations_wide, nasdaq_threshold, gold_threshold, config.REGIME_IDIOSYNCRATIC_THRESHOLD
                ).values
            )
            filtered_labels = apply_persistence_filter(raw_labels, config.REGIME_PERSISTENCE_MIN_DAYS)
            periods_df = build_regime_periods(dates, filtered_labels)

            label_shares = pd.Series(filtered_labels).value_counts(normalize=True)
            transition_starts = pd.to_datetime(periods_df["start_date"].iloc[1:])
            shift_survives_2026 = bool((transition_starts.dt.year == 2026).any())

            row = {
                "nasdaq_threshold": nasdaq_threshold,
                "gold_threshold": gold_threshold,
                "n_regime_periods": len(periods_df),
                "shift_survives_2026": shift_survives_2026,
            }
            for label in (
                config.REGIME_LABEL_RISK_ASSET,
                config.REGIME_LABEL_HARD_ASSET,
                config.REGIME_LABEL_IDIOSYNCRATIC,
                config.REGIME_LABEL_MIXED,
            ):
                row[f"share_{label}"] = float(label_shares.get(label, 0.0))
            rows.append(row)

    grid_df = pd.DataFrame(rows)
    config.OUTPUTS_TABLES_DIR.mkdir(parents=True, exist_ok=True)
    grid_df.to_csv(config.SENSITIVITY_GRID_TABLE_PATH, index=False)
    n_surviving = int(grid_df["shift_survives_2026"].sum())
    print(
        f"[regimes] sensitivity grid: {len(grid_df)} threshold combinations, "
        f"2026 shift survives in {n_surviving}/{len(grid_df)} -> {config.SENSITIVITY_GRID_TABLE_PATH}"
    )
    return grid_df


def build_label_stability_before_after(dates, raw_labels, filtered_labels):
    """
    Summarize how much the persistence filter changes label stability:
    run counts, run-length distribution, and day-to-day flip rate, before
    and after filtering.

    Why it exists: BUILD-SPEC section 6.4 requires documenting the
    persistence filter with a before/after comparison showing the raw
    labels flicker and the filtered ones don't -- this is the table
    behind that comparison and behind
    charts.plot_regime_label_stability_before_after().

    Parameters:
        dates: pandas.DatetimeIndex, chronological, same length as both
            label lists.
        raw_labels: list of str, one per date, from
            classify_regime_series() with no persistence filter applied.
        filtered_labels: list of str, one per date, from
            apply_persistence_filter().

    Returns:
        pandas.DataFrame with one row per ('raw', 'filtered'), columns
        stage, n_runs, median_run_length_days,
        pct_runs_shorter_than_min_days, n_day_to_day_flips,
        pct_days_flipped. Also written to
        config.REGIME_LABEL_STABILITY_TABLE_PATH.
    """

    def summarize(labels, stage):
        runs = _runs_from_labels(labels)
        lengths = [length for _, length in runs]
        n_flips = sum(1 for a, b in zip(labels[:-1], labels[1:]) if a != b)
        n_transitions = len(labels) - 1
        n_short_runs = sum(1 for length in lengths if length < config.REGIME_PERSISTENCE_MIN_DAYS)
        return {
            "stage": stage,
            "n_runs": len(runs),
            "median_run_length_days": float(np.median(lengths)),
            "pct_runs_shorter_than_min_days": 100 * n_short_runs / len(runs),
            "n_day_to_day_flips": n_flips,
            "pct_days_flipped": 100 * n_flips / n_transitions,
        }

    summary_df = pd.DataFrame([summarize(raw_labels, "raw"), summarize(filtered_labels, "filtered")])
    config.OUTPUTS_TABLES_DIR.mkdir(parents=True, exist_ok=True)
    summary_df.to_csv(config.REGIME_LABEL_STABILITY_TABLE_PATH, index=False)
    print(f"[regimes] wrote label-stability before/after summary -> {config.REGIME_LABEL_STABILITY_TABLE_PATH}")
    return summary_df


def main():
    """
    Classify Bitcoin's cross-asset regime for every day, apply the
    persistence filter, run the sensitivity grid, compute per-regime
    statistics, render the before/after label-stability diagnostic
    chart, and load regimes/regime_periods into the already-built
    btc_regime.db.

    Why it exists: this is the entry point src/run_all.py calls for
    Phase 5 (BUILD-SPEC section 12). Opens its own connection to
    config.DB_PATH, same pattern as correlations.main() -- Phase 3
    already created the schema. Calls charts.plot_regime_label_stability_before_after()
    directly here, rather than from charts.main(), because the raw
    (pre-persistence-filter) labels it needs don't persist anywhere --
    they only exist in memory at this point in the pipeline. Every other
    figure is generated later, by charts.main(), from data reloaded out
    of the database -- see docs/decisions-log.md.

    Parameters:
        None.

    Returns:
        None.
    """
    panel = load_panel()

    conn = sqlite3.connect(config.DB_PATH)
    try:
        correlations_wide = load_correlations_wide(conn)
        dates = correlations_wide.index

        raw_labels = list(
            classify_regime_series(
                correlations_wide,
                config.REGIME_NASDAQ_THRESHOLD,
                config.REGIME_GOLD_THRESHOLD,
                config.REGIME_IDIOSYNCRATIC_THRESHOLD,
            ).values
        )
        print(f"[regimes] classified {len(raw_labels)} days at baseline thresholds (no persistence filter)")

        filtered_labels = apply_persistence_filter(raw_labels, config.REGIME_PERSISTENCE_MIN_DAYS)

        regime_periods_df = build_regime_periods(dates, filtered_labels)
        regimes_daily_df = build_regimes_daily(dates, filtered_labels)
        print(
            f"[regimes] persistence filter ({config.REGIME_PERSISTENCE_MIN_DAYS}-day minimum): "
            f"{len(regime_periods_df)} regime periods"
        )

        build_label_stability_before_after(dates, raw_labels, filtered_labels)
        charts.plot_regime_label_stability_before_after(dates, raw_labels, filtered_labels)
        compute_regime_summary_statistics(regime_periods_df, panel)
        run_sensitivity_grid(correlations_wide)

        database.load_dataframe_to_table(conn, regimes_daily_df, "regimes")
        database.load_dataframe_to_table(conn, regime_periods_df, "regime_periods")
        conn.commit()
    finally:
        conn.close()


if __name__ == "__main__":
    main()
    sys.exit(0)
