"""
Shared read/write/lookup logic for data/raw/_manifest.json.

Why this file exists: fetch_market.py, fetch_fred.py, and fetch_sentiment.py
all need to record the same provenance fields (BUILD-SPEC section 5.4) and
all need the same same-day caching check, so that logic lives here once
instead of being copied into all three fetch modules.
"""

import json
from datetime import datetime, timezone

from src import config


def load_manifest():
    """
    Read the manifest file from disk.

    Why it exists: every fetch module needs to check what has already been
    pulled before hitting an API, per BUILD-SPEC section 5.4.

    Returns:
        dict keyed by "{source}_{series}", empty dict if no manifest exists yet.
    """
    if not config.MANIFEST_PATH.exists():
        return {}
    with open(config.MANIFEST_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def save_manifest(manifest):
    """
    Write the manifest dict back to disk as pretty-printed JSON.

    Why it exists: keeps the on-disk manifest format consistent no matter
    which fetch module last updated it.

    Parameters:
        manifest: dict keyed by "{source}_{series}".

    Returns:
        None.
    """
    config.RAW_DATA_DIR.mkdir(parents=True, exist_ok=True)
    with open(config.MANIFEST_PATH, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, sort_keys=True)


def manifest_key(source, series):
    """
    Build the dict key used to store one source/series pair in the manifest.

    Why it exists: keeps the key format identical everywhere it is used.

    Parameters:
        source: short source label, e.g. "yfinance", "fred", "alternative_me".
        series: ticker or series ID, e.g. "BTC-USD", "DFII10".

    Returns:
        str key, e.g. "yfinance_BTC-USD".
    """
    return f"{source}_{series}"


def has_fetched_today(manifest, source, series):
    """
    Check whether a source/series pair was already retrieved today (UTC).

    Why it exists: BUILD-SPEC section 12 requires that re-running the
    pipeline on the same day reads from cache instead of re-hitting the API.

    Parameters:
        manifest: dict as returned by load_manifest().
        source: short source label, e.g. "yfinance".
        series: ticker or series ID, e.g. "BTC-USD".

    Returns:
        bool, True if an entry exists whose retrieval date matches today's UTC date.
    """
    entry = manifest.get(manifest_key(source, series))
    if entry is None:
        return False
    retrieved_date = entry["retrieved_at_utc"][:10]
    today_utc_date = datetime.now(timezone.utc).date().isoformat()
    return retrieved_date == today_utc_date


def record_entry(manifest, *, source, series, row_count, first_date, last_date, library_version):
    """
    Add or update one manifest entry for a source/series pair.

    Why it exists: implements the exact provenance fields required by
    BUILD-SPEC section 5.4 in one place, so every fetch module records the
    same information the same way.

    Parameters:
        manifest: dict as returned by load_manifest(); mutated in place.
        source: short source label, e.g. "yfinance".
        series: ticker or series ID, e.g. "BTC-USD".
        row_count: int, number of rows retrieved.
        first_date: str, earliest date in the retrieved data (YYYY-MM-DD).
        last_date: str, latest date in the retrieved data (YYYY-MM-DD).
        library_version: str, version of the library used to fetch the data.

    Returns:
        the same manifest dict, updated.
    """
    retrieved_at_utc = datetime.now(timezone.utc).isoformat()
    manifest[manifest_key(source, series)] = {
        "source": source,
        "series": series,
        "retrieved_at_utc": retrieved_at_utc,
        "row_count": row_count,
        "first_date": first_date,
        "last_date": last_date,
        "library_version": library_version,
    }
    return manifest


def raw_filename(source, series):
    """
    Build the filename a raw CSV should be saved under.

    Why it exists: BUILD-SPEC section 5.4 fixes the naming pattern
    "{source}_{series}_{YYYYMMDD}.csv"; this keeps that pattern in one place.

    Parameters:
        source: short source label, e.g. "yfinance".
        series: ticker or series ID, e.g. "BTC-USD".

    Returns:
        Path under config.RAW_DATA_DIR.
    """
    today_utc_date = datetime.now(timezone.utc).strftime("%Y%m%d")
    safe_series = series.replace("/", "-")
    return config.RAW_DATA_DIR / f"{source}_{safe_series}_{today_utc_date}.csv"
