# Data dictionary

This file describes every dataset in the project, in the order the pipeline creates them: raw pulls, the daily panel, the SQLite database, and the tables in `outputs/tables/`.

## Market prices (yfinance, `data/raw/yfinance_*.csv`)

Daily OHLCV, `auto_adjust=True`, from 2018-02-01 through the run date. "Auto-adjusted" means Close already reflects splits and dividends, so I keep no separate "Adj Close" column.

| Ticker | What it is | Role in the analysis |
|---|---|---|
| `BTC-USD` | Bitcoin, priced in US dollars | The subject of the study |
| `^IXIC` | Nasdaq Composite index | Risk-asset benchmark, and the calendar anchor (see `docs/methodology.md`) |
| `^NDX` | Nasdaq 100 index | Secondary equity benchmark, used only for the validation comparison |
| `GC=F` | Gold futures (COMEX) | Robustness check for the gold series, used in validation |
| `GLD` | SPDR Gold Shares ETF | Headline gold series. It trades on equity-market hours, and `GC=F` trades nearly 24 hours |
| `DX-Y.NYB` | ICE US Dollar Index | Dollar-strength driver |
| `^GSPC` | S&P 500 index | Broad-equity control, loaded into the panel but not used in any finding |
| `^VIX` | CBOE Volatility Index | Risk-sentiment control, loaded into the panel but not used in any finding |

Bitcoin trades every calendar day. The equity and index tickers trade only on exchange days. Each series is pulled as-is, and the alignment happens when the panel is built.

## Macro series (FRED, `data/raw/fred_*.csv`)

Each row carries a `vintage_date`, which is FRED's `realtime_start`. FRED revises many series after first release. The vintage date tells a later reader which revision a number came from.

| Series ID | What it is | Frequency | Notes |
|---|---|---|---|
| `DFII10` | 10-year Treasury inflation-indexed (real) yield | Daily | The opportunity cost of holding a non-yielding asset. Used in one model feature |
| `DTWEXBGS` | Nominal Broad US Dollar Index | Daily | Official Fed dollar measure, a cross-check on `DX-Y.NYB` |
| `M2SL` | M2 money supply | Monthly | Forward-filled into the panel. The result is a step function (see `docs/methodology.md`) |
| `WALCL` | Federal Reserve balance sheet, total assets | Weekly | Forward-filled into the panel, with the same caveat as `M2SL` |
| `T10Y2Y` | 10-year minus 2-year Treasury yield spread | Daily | Macro-cycle control, not used in any finding |

FRED marks a missing observation with a literal `.`. I store it as `NaN` in the `value` column.

## Sentiment (`data/raw/alternative_me_crypto_fear_greed_index_*.csv`)

The Crypto Fear & Greed Index comes from `api.alternative.me`. It has daily values from 2018-02-01, scored 0 to 100, with a text label from "Extreme Fear" to "Extreme Greed".

The index is a composite that a third party builds from volatility, volume, social media activity, market dominance and search trends. The weighting is proprietary and unpublished. I cannot verify or reproduce it from raw data the way I can the price series. That is a limitation of every sentiment result in this project (`docs/limitations.md`).

I do not use the publisher's `fng_label` boundaries for my buckets. My buckets are `EXTREME_FEAR` for a value of 20 or below and `EXTREME_GREED` for 80 or above. The publisher's own "Extreme Fear" label covers 5 to 25 and its "Extreme Greed" covers 76 to 95.

## Provenance (`data/raw/_manifest.json`)

One entry per raw file. Each records the source, series identifier, retrieval time in UTC, row count, first and last date, and the library version used.

## Processed panel (`data/processed/panel_daily.parquet` and `panel_daily_alt_weekend.parquet`)

One row per Nasdaq trading date. Both files are gitignored and rebuilt by `python -m src.run_all`. They are identical except for `log_return_BTC-USD`. See `docs/methodology.md` for what differs and why.

| Column pattern | Meaning | Forward-filled? |
|---|---|---|
| `close_<ticker>` | Adjusted close on the Nasdaq calendar | No. Every market ticker covers all Nasdaq trading days, so this is never `NaN` |
| `volume_<ticker>` | Daily volume, same alignment | No |
| `log_return_<ticker>` | `ln(close_t / close_{t-1})`. The first row is `NaN` | No |
| `value_<series_id>` | FRED series value on the Nasdaq calendar | Only `M2SL` and `WALCL`. The three daily series are `NaN` on bond-market holidays that Nasdaq does not share |
| `is_forward_filled_<series_id>` | `True` on a date whose value was carried forward | Present for all 5 FRED series, and always `False` for the three daily ones |
| `fng_value` and `fng_label` | Fear & Greed score and label | No. `NaN` on the one known gap, 2018-04-16 |

The build asserts zero `NaN` in every `close_<ticker>` and `volume_<ticker>` column. That assertion caught a same-day publication lag in Bitcoin's data while I built the panel (see `docs/decisions-log.md`).

## SQLite database (`data/processed/btc_regime.db`)

The schema is in `sql/schema.sql`. Dates are stored as `YYYY-MM-DD` text, and every table has an index on `date`.

| Table | Grain | What it holds |
|---|---|---|
| `prices_daily` | date, ticker | Close and volume in long format |
| `returns_daily` | date, ticker | Daily log return |
| `macro_daily` | date, series_id | FRED values, plus `is_forward_filled` as 0 or 1 |
| `sentiment_daily` | date | `fng_value` and `fng_label` |
| `rolling_correlations` | date, pair, window, method | Correlation for `BTC_NASDAQ`, `BTC_GOLD` and `BTC_DXY`. `window` is 30 or 90. `method` is `pearson` or `spearman`. Spearman exists only for 90 days |
| `regimes` | date | Regime label and `regime_id` for each labelled day, after the persistence filter |
| `regime_periods` | regime_id | Start date, end date and length in trading days of each regime period |
| `returns_daily_recomputed_check` | date, ticker | Log returns recomputed independently, for query 7 |
| `rolling_correlations_recomputed_check` | date, pair, window, method | The hand-written 90-day Pearson values, for query 8 |
| `rolling_correlations_validation` | date, pair, window, method | 90-day Pearson for `BTC_NASDAQ_NDX` and `BTC_GOLD_GCF`, used only in validation |

## Output tables (`outputs/tables/`)

Every number quoted in `docs/` comes from one of these files.

| File | Made by | What it holds |
|---|---|---|
| `query_01_avg_correlation_by_year.csv` | SQL query 1 | Average 90-day Nasdaq and gold correlation per calendar year |
| `query_02_largest_btc_gold_correlation_moves.csv` | SQL query 2 | The 20 days with the largest one-day change in the 90-day gold correlation, with the Fear & Greed value |
| `query_03_forward_returns_by_sentiment_bucket.csv` | SQL query 3 | 20-day forward return by the publisher's five Fear & Greed labels. Not my buckets |
| `query_04_regime_duration_and_count.csv` | SQL query 4 | Count, total days and average length per regime type |
| `query_05_correlation_crossover_days.csv` | SQL query 5 | Days on which the Nasdaq and gold correlations swapped order |
| `query_06_btc_volatility_by_regime.csv` | SQL query 6 | Annualised Bitcoin volatility per regime type |
| `query_07_returns_reconciliation_check.csv` | SQL query 7 | Mismatches between stored and recomputed log returns. Zero rows means the check passed |
| `query_08_correlation_reconciliation_check.csv` | SQL query 8 | Mismatches between pandas and hand-written correlations. Zero rows means the check passed |
| `query_09_regime_timeline.csv` | SQL query 9 | The 16 regime periods |
| `query_10_sentiment_regime_crosstab.csv` | SQL query 10 | Days per sentiment bucket and regime label |
| `regime_summary_statistics.csv` | `src/regimes.py` | Annualised return and volatility, maximum drawdown and average Fear & Greed per regime period |
| `regime_label_stability_before_after.csv` | `src/regimes.py` | Run counts and flip rates before and after the persistence filter |
| `sensitivity_grid.csv` | `src/regimes.py` | Results for the 25 threshold pairs |
| `validation_comparison.csv` | `src/validation.py` | Published figures beside my computed values, with deltas and explanations |
| `sentiment_forward_returns_daily.csv` | `src/sentiment.py` | Forward log returns at 1, 5, 20 and 60 days for every day |
| `sentiment_forward_returns_summary.csv` | `src/sentiment.py` | n, mean, median and standard deviation by horizon and my sentiment bucket |
| `sentiment_transition_proximity.csv` | `src/sentiment.py` | Distance to the nearest regime boundary, by sentiment bucket |
| `ml_features_daily.csv` | `src/model.py` | The 2,045-row modelling dataset (columns below) |
| `ml_model_comparison.csv` | `src/model.py` | Accuracy, balanced accuracy and macro F1 for all four methods |
| `ml_per_fold_metrics.csv` | `src/model.py` | The same metrics per walk-forward fold |
| `ml_confusion_matrices.csv` | `src/model.py` | Confusion matrix counts for all four methods |
| `ml_class_support.csv` | `src/model.py` | Target days per regime |
| `robustness_weekend_handling.csv` | `src/robustness.py` | 90-day correlations with weekend returns absorbed versus dropped |
| `robustness_pearson_vs_spearman.csv` | `src/robustness.py` | How far the two methods differ, and on how many days |
| `robustness_window_30_vs_90.csv` | `src/robustness.py` | Spread and sign disagreement between the two windows |
| `correlation_latest_snapshot.csv` | `src/robustness.py` | The last 30-day and 90-day readings per pair |

Forward returns and returns in the model features are log returns. Annualised figures use 252 trading days.

**`ml_features_daily.csv` columns.** `corr_30_<pair>` and `corr_90_<pair>` are Pearson correlations for `BTC_NASDAQ`, `BTC_GOLD` and `BTC_DXY`. `realized_vol_20` is the 20-day standard deviation of Bitcoin log returns, annualised. `btc_momentum_20` is the sum of Bitcoin's last 20 log returns. `dxy_change_20` is the 20-day change in the dollar index, in index points. `real_yield_change_20` is the 20-day change in `DFII10`, in percentage points. `fng_level` and `fng_change_14` are the Fear & Greed value and its 14-day change. `regime_<label>` are the one-hot columns for the current regime. `current_regime_label` and `target_regime_label` are the label today and the label 5 trading days ahead.
