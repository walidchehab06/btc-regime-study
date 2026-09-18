"""
Merge the raw pulls from Phase 1 into one daily panel, per BUILD-SPEC-
bitcoin-regime-study.md section 12 (Phase 2).

Why this file exists: this is where the calendar alignment rule (section
6.1) and the returns-not-prices rule (section 6.2) actually get applied.
Builds two parquet files: the primary panel_daily.parquet, and
panel_daily_alt_weekend.parquet, the section 6.1 robustness-check panel
where Bitcoin's weekend returns are dropped instead of absorbed into
Monday's return.
"""

import sys

import numpy as np
import pandas as pd

from src import config


def load_latest_raw(source, series):
    """
    Load the most recently cached raw CSV for one source/series pair.

    Why it exists: Phase 1's fetch modules date-stamp every file they
    write, so building the panel needs to find the newest one rather than
    assume a fixed filename.

    Parameters:
        source: str, e.g. "yfinance", "fred", "alternative_me".
        series: str, ticker or series ID, e.g. "BTC-USD", "DFII10".

    Returns:
        pandas.DataFrame indexed by date (parsed as datetime), sorted ascending.

    Raises:
        RuntimeError if no cached file exists for this source/series.
    """
    matches = sorted(config.RAW_DATA_DIR.glob(f"{source}_{series}_*.csv"))
    if not matches:
        raise RuntimeError(
            f"No cached raw file found for {source}/{series}. "
            "Run `python -m src.run_all` to fetch it before building the panel."
        )
    latest_path = matches[-1]
    raw = pd.read_csv(latest_path, parse_dates=["date"], index_col="date")
    return raw.sort_index()


def build_nasdaq_calendar():
    """
    Build the trading-day calendar the whole panel is aligned to.

    Why it exists: implements BUILD-SPEC section 6.1's rule that every
    series is restricted to the days on which config.CALENDAR_ANCHOR_TICKER
    (Nasdaq Composite) traded.

    Parameters:
        None.

    Returns:
        pandas.DatetimeIndex of Nasdaq trading dates, sorted ascending.
    """
    nasdaq_raw = load_latest_raw(config.SOURCE_YFINANCE, config.CALENDAR_ANCHOR_TICKER)
    nasdaq_dates = nasdaq_raw.index
    assert not nasdaq_dates.duplicated().any(), "duplicate dates in the Nasdaq calendar itself"
    print(
        f"[build_panel] Nasdaq calendar (BUILD-SPEC 6.1 anchor): "
        f"{len(nasdaq_dates)} trading days, {nasdaq_dates.min().date()} to {nasdaq_dates.max().date()}"
    )
    return nasdaq_dates


def build_primary_market_block(nasdaq_dates):
    """
    Build close/volume/log-return columns for every market ticker, aligned
    to the Nasdaq calendar before returns are computed.

    Why it exists: this is the primary-panel version of BUILD-SPEC section
    6.1's calendar alignment and section 6.2's log-return rule. Aligning
    (reindexing) each ticker's price onto the Nasdaq calendar before taking
    the log difference is what makes Bitcoin's Monday return silently span
    the weekend: Saturday and Sunday are no longer adjacent rows once the
    series is reindexed, so `log(close_t / close_{t-1})` jumps straight
    from Friday to Monday.

    Parameters:
        nasdaq_dates: pandas.DatetimeIndex, the panel's date index.

    Returns:
        pandas.DataFrame indexed by nasdaq_dates, with close_<ticker>,
        volume_<ticker>, and log_return_<ticker> columns for every ticker
        in config.MARKET_TICKERS.
    """
    columns = {}
    for ticker in config.MARKET_TICKERS:
        raw = load_latest_raw(config.SOURCE_YFINANCE, ticker)
        rows_before = len(raw)

        aligned_close = raw["Close"].reindex(nasdaq_dates)
        aligned_volume = raw["Volume"].reindex(nasdaq_dates)
        log_return = np.log(aligned_close / aligned_close.shift(1))

        nan_count = aligned_close.isna().sum()
        print(
            f"[build_panel] {ticker}: {rows_before} rows before alignment -> "
            f"{len(aligned_close)} rows after aligning to Nasdaq calendar "
            f"({nan_count} NaN in close)"
        )

        columns[f"close_{ticker}"] = aligned_close
        columns[f"volume_{ticker}"] = aligned_volume
        columns[f"log_return_{ticker}"] = log_return

    return pd.DataFrame(columns, index=nasdaq_dates)


def build_alternative_btc_return(nasdaq_dates):
    """
    Build Bitcoin's log return the alternative way: computed on Bitcoin's
    own full daily calendar first, then aligned to the Nasdaq calendar.

    Why it exists: this is the BUILD-SPEC section 6.1 robustness check.
    Because the log return is taken on Bitcoin's native 365-day calendar
    *before* reindexing, Saturday and Sunday each get their own one-day
    return. Reindexing onto the Nasdaq calendar afterward then drops those
    weekend-only returns rather than folding them into Monday's figure, the
    opposite of build_primary_market_block()'s reindex-then-diff order.

    Parameters:
        nasdaq_dates: pandas.DatetimeIndex, the panel's date index.

    Returns:
        pandas.Series named "log_return_BTC-USD", indexed by nasdaq_dates.
    """
    raw = load_latest_raw(config.SOURCE_YFINANCE, "BTC-USD")
    full_calendar_log_return = np.log(raw["Close"] / raw["Close"].shift(1))

    aligned_return = full_calendar_log_return.reindex(nasdaq_dates)
    aligned_return.name = "log_return_BTC-USD"

    print(
        f"[build_panel] BTC-USD (alternative): {len(full_calendar_log_return)} "
        f"daily returns on Bitcoin's own calendar -> {aligned_return.notna().sum()} "
        "retained after aligning to Nasdaq calendar (weekend returns dropped, not absorbed)"
    )
    return aligned_return


def build_macro_block(nasdaq_dates):
    """
    Build value/is_forward_filled columns for every FRED series.

    Why it exists: implements BUILD-SPEC section 5.2's forward-fill rule.
    Monthly (M2SL) and weekly (WALCL) series are carried forward onto every
    Nasdaq trading day, with is_forward_filled=True marking a carried value
    so it is never mistaken for a genuine daily observation. The remaining
    series are aligned with no fill; any NaN there is left as NaN and is
    genuine publication lag, not missing data to be manufactured.

    Parameters:
        nasdaq_dates: pandas.DatetimeIndex, the panel's date index.

    Returns:
        pandas.DataFrame indexed by nasdaq_dates, with value_<series_id>
        and is_forward_filled_<series_id> columns for every series in
        config.FRED_SERIES.
    """
    columns = {}
    for series_id in config.FRED_SERIES:
        raw = load_latest_raw(config.SOURCE_FRED, series_id)
        rows_before = len(raw)

        if series_id in config.FRED_FORWARD_FILL_SERIES:
            aligned_value = raw["value"].reindex(nasdaq_dates, method="ffill")
            was_not_an_original_date = pd.Series(~nasdaq_dates.isin(raw.index), index=nasdaq_dates)
            is_forward_filled = was_not_an_original_date & aligned_value.notna()
            fill_note = "forward-filled"
        else:
            aligned_value = raw["value"].reindex(nasdaq_dates)
            is_forward_filled = pd.Series(False, index=nasdaq_dates)
            fill_note = "not filled"

        nan_count = aligned_value.isna().sum()
        print(
            f"[build_panel] {series_id}: {rows_before} rows before alignment -> "
            f"{len(aligned_value)} rows after aligning to Nasdaq calendar "
            f"({fill_note}, {nan_count} NaN)"
        )

        columns[f"value_{series_id}"] = aligned_value
        columns[f"is_forward_filled_{series_id}"] = is_forward_filled

    return pd.DataFrame(columns, index=nasdaq_dates)


def build_sentiment_block(nasdaq_dates):
    """
    Build fng_value/fng_label columns aligned to the Nasdaq calendar.

    Why it exists: the Fear & Greed Index is not in BUILD-SPEC section
    5.2's forward-fill list, so any day it wasn't published (the single
    known gap at 2018-04-16) is left as NaN rather than carried forward.

    Parameters:
        nasdaq_dates: pandas.DatetimeIndex, the panel's date index.

    Returns:
        pandas.DataFrame indexed by nasdaq_dates, with fng_value and
        fng_label columns.
    """
    raw = load_latest_raw(config.SOURCE_SENTIMENT, config.SENTIMENT_SERIES_NAME)
    rows_before = len(raw)

    aligned_value = raw["fng_value"].reindex(nasdaq_dates)
    aligned_label = raw["fng_label"].reindex(nasdaq_dates)

    nan_count = aligned_value.isna().sum()
    print(
        f"[build_panel] sentiment: {rows_before} rows before alignment -> "
        f"{len(aligned_value)} rows after aligning to Nasdaq calendar ({nan_count} NaN)"
    )

    return pd.DataFrame(
        {"fng_value": aligned_value, "fng_label": aligned_label}, index=nasdaq_dates
    )


def assert_primary_panel_integrity(panel, nasdaq_dates):
    """
    Fail loudly on any NaN pattern that isn't already documented and expected.

    Why it exists: BUILD-SPEC section 11 requires assertions at data-
    integrity boundaries. Every threshold here came from actually
    inspecting the raw data, not from a guess: the trailing-30-day
    tolerance on market columns caught a real same-day BTC-USD
    publication-lag gap that resolved on refetch; the NaN-fraction
    tolerance on daily FRED columns accounts for bond-market holidays
    (Columbus Day, Veterans Day) that aren't Nasdaq holidays; the
    exactly-one NaN expected in sentiment is the documented 2018-04-16 gap.
    See docs/decisions-log.md for all three.

    Parameters:
        panel: pandas.DataFrame, the assembled primary panel.
        nasdaq_dates: pandas.DatetimeIndex, the panel's date index.

    Returns:
        None.

    Raises:
        AssertionError if any check fails.
    """
    assert not panel.index.duplicated().any(), "duplicate dates in the assembled panel"
    assert len(panel) == len(nasdaq_dates), "panel row count does not match the Nasdaq calendar"

    trailing_cutoff = nasdaq_dates.max() - pd.Timedelta(days=30)

    for ticker in config.MARKET_TICKERS:
        close_col = f"close_{ticker}"
        volume_col = f"volume_{ticker}"
        for column_name in (close_col, volume_col):
            nan_dates = panel.index[panel[column_name].isna()]
            if len(nan_dates) > 0:
                assert nan_dates.min() > trailing_cutoff, (
                    f"{column_name} has a NaN at {nan_dates.min().date()}, older than the "
                    "trailing 30-day window where a vendor publication lag is plausible "
                    "(BTC-USD showed this with a same-day gap that resolved on refetch a "
                    "few hours later, see docs/decisions-log.md). This looks like a real "
                    "gap, not lag. Investigate before proceeding."
                )

    for series_id in config.FRED_SERIES:
        if series_id in config.FRED_FORWARD_FILL_SERIES:
            continue
        value_col = f"value_{series_id}"
        nan_fraction = panel[value_col].isna().sum() / len(panel)
        assert nan_fraction <= config.FRED_DAILY_MAX_NAN_FRACTION, (
            f"{value_col} is {nan_fraction:.1%} NaN, above the "
            f"{config.FRED_DAILY_MAX_NAN_FRACTION:.0%} tolerance for bond-market-holiday "
            "gaps (Columbus Day, Veterans Day, and similar) -- this looks like a real "
            "gap, not an expected calendar mismatch. Investigate before proceeding."
        )

    fng_nan_count = panel["fng_value"].isna().sum()
    assert fng_nan_count == 1, (
        f"expected exactly 1 NaN in fng_value (the documented 2018-04-16 gap), "
        f"found {fng_nan_count}. The source data may have changed shape since this "
        "assertion was written. Investigate before proceeding."
    )


def print_panel_summary(panel, label):
    """
    Print the row count, date range, and per-column null counts for a panel.

    Why it exists: BUILD-SPEC section 12's Phase 2 acceptance criteria
    requires a printed summary with exactly these three things.

    Parameters:
        panel: pandas.DataFrame.
        label: str, a short name for which panel this is, for the log line.

    Returns:
        None.
    """
    print(f"[build_panel] --- {label} panel summary ---")
    print(f"[build_panel] rows: {len(panel)}, columns: {len(panel.columns)}")
    print(f"[build_panel] date range: {panel.index.min().date()} to {panel.index.max().date()}")
    null_counts = panel.isna().sum()
    for column_name, null_count in null_counts.items():
        if null_count > 0:
            print(f"[build_panel]   {column_name}: {null_count} NaN")


def build_primary_panel(nasdaq_dates):
    """
    Assemble the primary daily panel: market, macro, and sentiment blocks
    merged onto the Nasdaq calendar.

    Why it exists: this is panel_daily.parquet, the main deliverable of
    Phase 2 (BUILD-SPEC section 12).

    Parameters:
        nasdaq_dates: pandas.DatetimeIndex, the panel's date index.

    Returns:
        pandas.DataFrame indexed by date.
    """
    market_block = build_primary_market_block(nasdaq_dates)
    macro_block = build_macro_block(nasdaq_dates)
    sentiment_block = build_sentiment_block(nasdaq_dates)

    panel = pd.concat([market_block, macro_block, sentiment_block], axis=1)
    panel.index.name = "date"
    print(f"[build_panel] merged all blocks: {len(panel)} rows, {len(panel.columns)} columns")

    assert_primary_panel_integrity(panel, nasdaq_dates)
    print_panel_summary(panel, "primary")
    return panel


def build_alternative_weekend_panel(primary_panel, nasdaq_dates):
    """
    Build the section 6.1 robustness-check panel.

    Why it exists: swaps only log_return_BTC-USD for the weekend-dropped
    version (see build_alternative_btc_return()); every other column is
    identical to the primary panel, which keeps this an isolated test of
    the one design choice section 6.1 asks to be checked.

    Parameters:
        primary_panel: pandas.DataFrame, the output of build_primary_panel().
        nasdaq_dates: pandas.DatetimeIndex, the panel's date index.

    Returns:
        pandas.DataFrame indexed by date.
    """
    alt_panel = primary_panel.copy()
    alt_panel["log_return_BTC-USD"] = build_alternative_btc_return(nasdaq_dates)
    print_panel_summary(alt_panel, "alternative weekend-dropped")
    return alt_panel


def main():
    """
    Build and save both daily panels.

    Why it exists: this is the entry point src/run_all.py calls for the
    panel-construction step of Phase 2 (BUILD-SPEC section 12).

    Parameters:
        None.

    Returns:
        None.
    """
    config.PROCESSED_DATA_DIR.mkdir(parents=True, exist_ok=True)

    nasdaq_dates = build_nasdaq_calendar()

    primary_panel = build_primary_panel(nasdaq_dates)
    primary_panel.to_parquet(config.PANEL_PATH)
    print(f"[build_panel] saved primary panel to {config.PANEL_PATH}")

    alt_panel = build_alternative_weekend_panel(primary_panel, nasdaq_dates)
    alt_panel.to_parquet(config.PANEL_ALT_WEEKEND_PATH)
    print(f"[build_panel] saved alternative panel to {config.PANEL_ALT_WEEKEND_PATH}")


if __name__ == "__main__":
    main()
    sys.exit(0)
