"""
Tests for src/manifest.py's caching and round-trip logic.

Why this file exists: BUILD-SPEC-bitcoin-regime-study.md section 11 requires
a handful of real tests; the manifest is the piece of Phase 1 logic that
decides whether an API gets hit again, so a silent bug here would mean
either stale data or needless re-fetching without anyone noticing.
"""

from datetime import datetime, timedelta, timezone

from src import manifest


def test_record_entry_round_trips_through_save_and_load(tmp_path, monkeypatch):
    manifest_path = tmp_path / "_manifest.json"
    monkeypatch.setattr(manifest.config, "RAW_DATA_DIR", tmp_path)
    monkeypatch.setattr(manifest.config, "MANIFEST_PATH", manifest_path)

    empty_manifest = manifest.load_manifest()
    assert empty_manifest == {}

    updated_manifest = manifest.record_entry(
        empty_manifest,
        source="yfinance",
        series="BTC-USD",
        row_count=100,
        first_date="2018-02-01",
        last_date="2026-09-18",
        library_version="1.7.0",
    )
    manifest.save_manifest(updated_manifest)

    reloaded_manifest = manifest.load_manifest()
    entry = reloaded_manifest["yfinance_BTC-USD"]
    assert entry["row_count"] == 100
    assert entry["first_date"] == "2018-02-01"
    assert entry["last_date"] == "2026-09-18"
    assert entry["library_version"] == "1.7.0"


def test_has_fetched_today_true_when_retrieved_today():
    today_utc = datetime.now(timezone.utc).isoformat()
    fake_manifest = {
        "yfinance_BTC-USD": {
            "source": "yfinance",
            "series": "BTC-USD",
            "retrieved_at_utc": today_utc,
            "row_count": 1,
            "first_date": "2018-02-01",
            "last_date": "2018-02-01",
            "library_version": "1.7.0",
        }
    }
    assert manifest.has_fetched_today(fake_manifest, "yfinance", "BTC-USD") is True


def test_has_fetched_today_false_when_retrieved_yesterday():
    yesterday_utc = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
    fake_manifest = {
        "yfinance_BTC-USD": {
            "source": "yfinance",
            "series": "BTC-USD",
            "retrieved_at_utc": yesterday_utc,
            "row_count": 1,
            "first_date": "2018-02-01",
            "last_date": "2018-02-01",
            "library_version": "1.7.0",
        }
    }
    assert manifest.has_fetched_today(fake_manifest, "yfinance", "BTC-USD") is False


def test_has_fetched_today_false_when_no_entry():
    assert manifest.has_fetched_today({}, "yfinance", "BTC-USD") is False
