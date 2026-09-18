"""
Pull macro series from the FRED API for every series in config.FRED_SERIES.

Why this file exists: BUILD-SPEC-bitcoin-regime-study.md section 5.2 requires
these exact FRED series, cached to disk with the publication vintage date
recorded, and requires the pipeline to stop rather than fetch silently if
the FRED_API_KEY is missing.
"""

import os
import sys

import pandas as pd
import requests
from dotenv import load_dotenv

from src import config, manifest


def get_fred_api_key():
    """
    Read FRED_API_KEY from the environment (.env file).

    Why it exists: BUILD-SPEC section 4 requires stopping and reporting
    rather than proceeding if a required data source is unavailable, and a
    missing key means FRED cannot be reached at all.

    Parameters:
        None.

    Returns:
        str, the API key.

    Raises:
        RuntimeError if the key is missing or blank.
    """
    load_dotenv()
    api_key = os.environ.get(config.FRED_API_KEY_ENV_VAR, "").strip()
    if not api_key:
        raise RuntimeError(
            f"{config.FRED_API_KEY_ENV_VAR} is not set in .env. "
            "Get a free key at https://fred.stlouisfed.org/docs/api/api_key.html "
            "and add it to .env before running this pipeline."
        )
    return api_key


def fetch_one_series(series_id, api_key):
    """
    Pull one FRED series' full observation history.

    Why it exists: isolates the actual API call so fetch_all_series() can
    focus on caching, logging, and the manifest.

    Parameters:
        series_id: str, a FRED series ID, e.g. "DFII10".
        api_key: str, the FRED API key.

    Returns:
        pandas.DataFrame indexed by date (str, YYYY-MM-DD) with columns
        "value" (float, NaN where FRED reports no observation) and
        "vintage_date" (str, the realtime_start date FRED returned).

    Raises:
        RuntimeError if FRED returns no observations for this series.
    """
    response = requests.get(
        config.FRED_BASE_URL,
        params={
            "series_id": series_id,
            "api_key": api_key,
            "file_type": "json",
            "observation_start": config.STUDY_START_DATE,
        },
    )
    response.raise_for_status()
    observations = response.json()["observations"]

    if not observations:
        raise RuntimeError(
            f"FRED returned no observations for series '{series_id}'. "
            "This usually means the series ID changed or was discontinued. "
            "Check https://fred.stlouisfed.org for the current series ID "
            "before substituting anything, per BUILD-SPEC section 5.2."
        )

    dates = [obs["date"] for obs in observations]
    values = [
        float("nan") if obs["value"] == "." else float(obs["value"])
        for obs in observations
    ]
    vintage_dates = [obs["realtime_start"] for obs in observations]

    series_df = pd.DataFrame(
        {"value": values, "vintage_date": vintage_dates}, index=pd.Index(dates, name="date")
    )
    return series_df


def fetch_all_series():
    """
    Fetch every series in config.FRED_SERIES, using the cache where possible.

    Why it exists: this is the entry point src/run_all.py calls for the
    macro-data step of Phase 1 (BUILD-SPEC section 12).

    Parameters:
        None.

    Returns:
        None. Writes one CSV per series to data/raw/ and updates the manifest.
    """
    config.RAW_DATA_DIR.mkdir(parents=True, exist_ok=True)
    current_manifest = manifest.load_manifest()

    already_cached = all(
        manifest.has_fetched_today(current_manifest, config.SOURCE_FRED, series_id)
        for series_id in config.FRED_SERIES
    )
    api_key = None if already_cached else get_fred_api_key()

    for series_id, description in config.FRED_SERIES.items():
        if manifest.has_fetched_today(current_manifest, config.SOURCE_FRED, series_id):
            print(f"[fetch_fred] {series_id}: already fetched today, using cache")
            continue

        print(f"[fetch_fred] {series_id}: fetching ({description})")
        series_df = fetch_one_series(series_id, api_key)

        out_path = manifest.raw_filename(config.SOURCE_FRED, series_id)
        series_df.to_csv(out_path)

        row_count = len(series_df)
        first_date = series_df.index.min()
        last_date = series_df.index.max()
        print(
            f"[fetch_fred] {series_id}: {row_count} rows, "
            f"{first_date} to {last_date}, saved to {out_path}"
        )

        manifest.record_entry(
            current_manifest,
            source=config.SOURCE_FRED,
            series=series_id,
            row_count=row_count,
            first_date=first_date,
            last_date=last_date,
            library_version=requests.__version__,
        )
        manifest.save_manifest(current_manifest)


if __name__ == "__main__":
    fetch_all_series()
    sys.exit(0)
