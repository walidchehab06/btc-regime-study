# Bitcoin Cross-Asset Regime Study

What kind of asset has Bitcoin behaved like, and when did that change?

## What it does

I measure how Bitcoin's daily returns move with Nasdaq, gold and the US dollar index, using rolling 30-day and 90-day correlations from February 2018 to September 2026. I sort each day into one of four regimes with transparent rules, and I test how much the result depends on my thresholds. I check whether Fear & Greed extremes line up with regime changes, compare my correlations with published institutional figures, and test whether a small model can predict the next regime.

The project is descriptive. It makes no price forecasts and gives no trading signals.

## Data

Everything is free and public. Prices come from yfinance (Bitcoin, Nasdaq Composite, Nasdaq 100, gold futures, the GLD ETF, the dollar index, the S&P 500 and the VIX). Five macro series come from FRED. Sentiment is the Crypto Fear & Greed Index, a third-party composite whose construction is proprietary.

The raw pulls in `data/raw/` total about 2 MB, so I commit them. `data/raw/_manifest.json` records the source, retrieval time, row count and date range of every file.

## How to run

You need Windows PowerShell and Python 3.11 or later. I ran 3.14.7.

```
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python -m src.run_all
pytest tests/
```

`python -m src.run_all` rebuilds every table in `outputs/tables/` and every figure in `outputs/figures/`. It replaces a Makefile, because I do not have `make` installed.

The fetch cache is valid for one UTC day. On 2026-09-18 the run reads the committed files and needs no API key. On any later day a fresh clone fetches new data instead, and the run fails unless `.env` holds a `FRED_API_KEY` (copy `.env.example` and add a free key from FRED). The numbers then differ from those below.

## Headline findings

1. **Nasdaq has been Bitcoin's stronger link in 8 of 9 calendar years.** On 2026-09-17 the 90-day correlation is 0.58 with gold and 0.38 with Nasdaq. The 2026 gold average is only 0.29, so the rise is recent. See `correlation_latest_snapshot.csv` and figure 1.

2. **The regime label changed from RISK_ASSET to HARD_ASSET on 2026-08-06.** A regime transition falls in 2026 for all 25 threshold pairs I tested. The new period is 30 trading days old. See `query_09_regime_timeline.csv`, `sensitivity_grid.csv` and figures 3 and 5.

3. **Neither model beats the persistence baseline.** Predicting "no change" scores 0.96 accuracy. The decision tree scores 0.84 and the logistic regression 0.68. This is the expected result, because the labels come from a 90-day window. See `ml_model_comparison.csv` and figure 8.

The tables are in `outputs/tables/`, and each finding in `docs/findings.md` carries its own caveat.

## Where the detail lives

| File | Contents |
|---|---|
| `docs/findings.md` | Five findings, each with numbers, a figure and a caveat |
| `docs/methodology.md` | Every analytical choice, in plain English |
| `docs/validation.md` | My correlations against published Grayscale and Bitwise figures |
| `docs/limitations.md` | What the analysis cannot tell you |
| `docs/ml-caveats.md` | Why the classifier is exploratory |
| `docs/data-dictionary.md` | Every dataset, table and column |
| `docs/sources.md` | Citations for every external figure |
| `docs/decisions-log.md` | Each non-obvious decision, with alternatives and reasons |
| `docs/future-work.md` | Ideas I left out of version 1 |

The code is in `src/`, the SQL in `sql/`, and the tests in `tests/`. A build specification directed construction, but it is not included in this repository. `docs/methodology.md` and `docs/decisions-log.md` record what I built and why.
