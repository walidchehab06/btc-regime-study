"""
Pull daily OHLCV price history for every ticker in config.MARKET_TICKERS.

Why this file exists: BUILD-SPEC-bitcoin-regime-study.md section 5.1 requires
these exact tickers, pulled with auto_adjust=True from the study start date,
cached to disk with no silent substitution if a ticker fails.
"""

import sys

import yfinance as yf

from src import config, manifest

OHLCV_COLUMNS = ["Open", "High", "Low", "Close", "Volume"]


def fetch_one_ticker(ticker):
    """
    Pull one ticker's daily OHLCV history from yfinance.

    Why it exists: isolates the actual API call so fetch_all_tickers() can
    focus on caching, logging, and the manifest.

    Parameters:
        ticker: str, a yfinance ticker symbol.

    Returns:
        pandas.DataFrame indexed by UTC calendar date (str, YYYY-MM-DD),
        with columns Open, High, Low, Close, Volume.

    Raises:
        RuntimeError if yfinance returns no rows for this ticker.
    """
    raw = yf.Ticker(ticker).history(
        start=config.STUDY_START_DATE, auto_adjust=True
    )
    if raw.empty:
        raise RuntimeError(
            f"yfinance returned no data for ticker '{ticker}'. "
            "This usually means the symbol changed or was delisted. "
            "Check https://finance.yahoo.com for the current symbol "
            "before substituting anything, per BUILD-SPEC section 5.1."
        )
    prices = raw[OHLCV_COLUMNS].copy()
    prices.index = prices.index.tz_convert("UTC").date
    prices.index.name = "date"
    return prices


def fetch_all_tickers():
    """
    Fetch every ticker in config.MARKET_TICKERS, using the cache where possible.

    Why it exists: this is the entry point src/run_all.py calls for the
    market-data step of Phase 1 (BUILD-SPEC section 12).

    Parameters:
        None.

    Returns:
        None. Writes one CSV per ticker to data/raw/ and updates the manifest.
    """
    config.RAW_DATA_DIR.mkdir(parents=True, exist_ok=True)
    current_manifest = manifest.load_manifest()

    for ticker, role in config.MARKET_TICKERS.items():
        if manifest.has_fetched_today(current_manifest, config.SOURCE_YFINANCE, ticker):
            print(f"[fetch_market] {ticker}: already fetched today, using cache")
            continue

        print(f"[fetch_market] {ticker}: fetching ({role})")
        prices = fetch_one_ticker(ticker)

        out_path = manifest.raw_filename(config.SOURCE_YFINANCE, ticker)
        prices.to_csv(out_path)

        row_count = len(prices)
        first_date = str(prices.index.min())
        last_date = str(prices.index.max())
        print(
            f"[fetch_market] {ticker}: {row_count} rows, "
            f"{first_date} to {last_date}, saved to {out_path}"
        )

        manifest.record_entry(
            current_manifest,
            source=config.SOURCE_YFINANCE,
            series=ticker,
            row_count=row_count,
            first_date=first_date,
            last_date=last_date,
            library_version=yf.__version__,
        )
        manifest.save_manifest(current_manifest)


if __name__ == "__main__":
    fetch_all_tickers()
    sys.exit(0)
