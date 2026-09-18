# Data dictionary

This document is built up phase by phase as sources are added to the
pipeline. Phase 1 (data acquisition) adds the raw sources below; later
phases add the derived panel columns (log returns, rolling correlations,
regime labels) as they are computed.

## Market prices (yfinance, `data/raw/yfinance_*.csv`)

Daily OHLCV, `auto_adjust=True`, from 2018-02-01 through the run date.
"Auto-adjusted" means Close already reflects splits and dividends, so no
separate "Adj Close" column is kept.

| Ticker | What it is | Role in the analysis |
|---|---|---|
| `BTC-USD` | Bitcoin, priced in US dollars | The subject of the study |
| `^IXIC` | Nasdaq Composite index | Risk-asset / tech-equity benchmark; also the calendar anchor (see docs/methodology.md, Phase 2) |
| `^NDX` | Nasdaq 100 index | Secondary equity benchmark, used only for the validation comparison |
| `GC=F` | Gold futures (COMEX) | Hard-asset benchmark |
| `GLD` | SPDR Gold Shares ETF | Robustness check against `GC=F`; trades on equity-market hours, `GC=F` trades nearly 24 hours |
| `DX-Y.NYB` | ICE US Dollar Index | Dollar-strength driver |
| `^GSPC` | S&P 500 index | Broad-equity control |
| `^VIX` | CBOE Volatility Index | Risk-sentiment control |

Bitcoin trades every calendar day; the equity and index tickers only trade
on exchange trading days. Phase 1 pulls each series as-is; the calendar
alignment decision (restricting the merged panel to Nasdaq trading days) is
made in Phase 2 and documented in docs/methodology.md.

## Macro series (FRED, `data/raw/fred_*.csv`)

Each row carries a `vintage_date` (FRED's `realtime_start`), the date FRED
considers this value to have been current as of. FRED revises many series
after initial release; the vintage date is what lets a later reader tell
which revision a given number came from.

| Series ID | What it is | Frequency | Notes |
|---|---|---|---|
| `DFII10` | 10-year Treasury inflation-indexed (real) yield | Daily | The opportunity cost of holding a non-yielding asset like gold or Bitcoin |
| `DTWEXBGS` | Nominal Broad US Dollar Index | Daily | Official Fed dollar measure; cross-check against `DX-Y.NYB` |
| `M2SL` | M2 money supply | Monthly | Forward-filled into the daily panel in Phase 2; this creates a step function, not smooth daily variation — see docs/methodology.md |
| `WALCL` | Federal Reserve balance sheet, total assets | Weekly | Forward-filled into the daily panel in Phase 2, same caveat as `M2SL` |
| `T10Y2Y` | 10-year minus 2-year Treasury yield spread | Daily | Macro-cycle control |

A missing observation from FRED is stored as `NaN` in the `value` column
(FRED itself marks these with a literal `.`).

## Sentiment (`data/raw/alternative_me_crypto_fear_greed_index_*.csv`)

The Crypto Fear & Greed Index, pulled from `api.alternative.me`, daily
values from 2018-02-01 to present, scored 0-100 with a text label
("Extreme Fear" through "Extreme Greed").

This index is a composite built by a third party from volatility, volume,
social media activity, market dominance, and search trends. Its exact
construction (the weighting of those inputs) is proprietary and not
published, so it cannot be independently verified or reproduced from raw
data the way the price-based series above can. Treat it as a documented
limitation, not a hidden one, wherever it is used in the analysis.
