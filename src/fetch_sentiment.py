"""
Pull the full history of the Crypto Fear & Greed Index.

Why this file exists: BUILD-SPEC-bitcoin-regime-study.md section 5.3 requires
this single series, pulled from its documented "limit=0" (full history)
endpoint, with field names read from the live response rather than assumed.
"""

import sys
from datetime import datetime, timezone

import pandas as pd
import requests

from src import config, manifest


def fetch_sentiment_history():
    """
    Pull the full Fear & Greed Index history from alternative.me.

    Why it exists: isolates the actual API call so fetch_and_cache_sentiment()
    can focus on caching, logging, and the manifest.

    Parameters:
        None.

    Returns:
        pandas.DataFrame indexed by UTC calendar date (str, YYYY-MM-DD) with
        columns "fng_value" (int) and "fng_label" (str), e.g. "Extreme Fear".

    Raises:
        RuntimeError if the API returns no data points.
    """
    response = requests.get(config.SENTIMENT_URL)
    response.raise_for_status()
    payload = response.json()
    entries = payload["data"]

    if not entries:
        raise RuntimeError(
            "alternative.me returned no Fear & Greed data. "
            "Check https://alternative.me/crypto/fear-and-greed-index/ "
            "for API status before substituting anything, per BUILD-SPEC section 5.3."
        )

    dates = [
        datetime.fromtimestamp(int(entry["timestamp"]), tz=timezone.utc).date().isoformat()
        for entry in entries
    ]
    fng_values = [int(entry["value"]) for entry in entries]
    fng_labels = [entry["value_classification"] for entry in entries]

    sentiment_df = pd.DataFrame(
        {"fng_value": fng_values, "fng_label": fng_labels},
        index=pd.Index(dates, name="date"),
    ).sort_index()
    return sentiment_df


def fetch_and_cache_sentiment():
    """
    Fetch the Fear & Greed history, using the cache where possible.

    Why it exists: this is the entry point src/run_all.py calls for the
    sentiment-data step of Phase 1 (BUILD-SPEC section 12).

    Parameters:
        None.

    Returns:
        None. Writes one CSV to data/raw/ and updates the manifest.
    """
    config.RAW_DATA_DIR.mkdir(parents=True, exist_ok=True)
    current_manifest = manifest.load_manifest()

    if manifest.has_fetched_today(
        current_manifest, config.SOURCE_SENTIMENT, config.SENTIMENT_SERIES_NAME
    ):
        print(
            f"[fetch_sentiment] {config.SENTIMENT_SERIES_NAME}: "
            "already fetched today, using cache"
        )
        return

    print(f"[fetch_sentiment] {config.SENTIMENT_SERIES_NAME}: fetching")
    sentiment_df = fetch_sentiment_history()

    out_path = manifest.raw_filename(config.SOURCE_SENTIMENT, config.SENTIMENT_SERIES_NAME)
    sentiment_df.to_csv(out_path)

    row_count = len(sentiment_df)
    first_date = sentiment_df.index.min()
    last_date = sentiment_df.index.max()
    print(
        f"[fetch_sentiment] {config.SENTIMENT_SERIES_NAME}: {row_count} rows, "
        f"{first_date} to {last_date}, saved to {out_path}"
    )

    manifest.record_entry(
        current_manifest,
        source=config.SOURCE_SENTIMENT,
        series=config.SENTIMENT_SERIES_NAME,
        row_count=row_count,
        first_date=first_date,
        last_date=last_date,
        library_version=requests.__version__,
    )
    manifest.save_manifest(current_manifest)


if __name__ == "__main__":
    fetch_and_cache_sentiment()
    sys.exit(0)
