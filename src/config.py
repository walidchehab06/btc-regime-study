"""
Central place for every tunable value used by the data-acquisition pipeline.

Why this file exists: BUILD-SPEC-bitcoin-regime-study.md section 11 requires
that all tunable parameters (dates, tickers, series IDs, file paths) live
here and nowhere else, so that changing one of them is a one-line edit
instead of a search through every module.
"""

from pathlib import Path

# --- Study window (BUILD-SPEC section 5.1) ---
# 2018-02-01 is the day the Fear & Greed Index history begins, so every
# other series is pulled from the same start date for a common baseline.
STUDY_START_DATE = "2018-02-01"

# --- Market prices, pulled via yfinance (BUILD-SPEC section 5.1) ---
# Ticker -> role in the analysis, used for logging and for docs/data-dictionary.md.
MARKET_TICKERS = {
    "BTC-USD": "Bitcoin - the subject of the study",
    "^IXIC": "Nasdaq Composite - risk-asset / tech-equity benchmark, also the calendar anchor",
    "^NDX": "Nasdaq 100 - secondary equity benchmark, used for the validation comparison",
    "GC=F": "Gold futures - hard-asset benchmark",
    "GLD": "Gold ETF - robustness check against GC=F (different trading hours)",
    "DX-Y.NYB": "US Dollar Index - dollar-strength driver",
    "^GSPC": "S&P 500 - broad-equity control",
    "^VIX": "CBOE Volatility Index - risk-sentiment control",
}

# --- Macro series, pulled from FRED (BUILD-SPEC section 5.2) ---
# Series ID -> what it is, used for logging and for docs/data-dictionary.md.
FRED_SERIES = {
    "DFII10": "10-year Treasury inflation-indexed (real) yield",
    "DTWEXBGS": "Nominal Broad US Dollar Index",
    "M2SL": "M2 money supply (monthly, forward-filled into the daily panel)",
    "WALCL": "Fed balance sheet, total assets (weekly, forward-filled into the daily panel)",
    "T10Y2Y": "10y-2y Treasury spread",
}
FRED_BASE_URL = "https://api.stlouisfed.org/fred/series/observations"
FRED_API_KEY_ENV_VAR = "FRED_API_KEY"

# --- Sentiment, pulled from alternative.me (BUILD-SPEC section 5.3) ---
SENTIMENT_URL = "https://api.alternative.me/fng/?limit=0&format=json"
SENTIMENT_SERIES_NAME = "crypto_fear_greed_index"

# --- Source labels used consistently across fetch modules and the manifest ---
SOURCE_YFINANCE = "yfinance"
SOURCE_FRED = "fred"
SOURCE_SENTIMENT = "alternative_me"

# --- Caching and provenance (BUILD-SPEC section 5.4) ---
RAW_DATA_DIR = Path("data/raw")
MANIFEST_PATH = RAW_DATA_DIR / "_manifest.json"
