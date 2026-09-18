# Limitations

This file lists what the analysis cannot tell you. Where a limitation has a number behind it, I give the number and the file it comes from.

## Correlation is not causation

The study measures how Bitcoin's daily returns moved with other assets' daily returns. It does not test why. Commentary ties the recent shift to a "debasement trade", meaning US debt and deficits. I do not test that story. The M2 and Fed balance sheet series sit in the panel, but no finding depends on them.

## Regime labels are constructed, not observed

Nobody observed Bitcoin "becoming" a hard asset. I defined four labels with thresholds I chose (0.40 for Nasdaq, 0.35 for gold, 0.25 for the idiosyncratic band) and a 15-day persistence filter. Across the 25 threshold pairs in `outputs/tables/sensitivity_grid.csv`, the number of regime periods ranges from 13 to 17. The RISK_ASSET share of days ranges from 25% to 46%. A different rule would draw different boundaries, and no rule is the true one.

The first label is dated 2018-06-12, because the first 90-day window needs 90 days of returns. The study has no regime label for the first months of the sample.

## The Fear & Greed Index is a proprietary composite

The publisher, alternative.me, does not disclose the exact weights of its inputs. I cannot reproduce or audit the index. The index has no value for 2018-04-16, and I left that day empty instead of filling it. My extreme-fear and extreme-greed buckets (20 or below, 80 or above) are not the publisher's own label boundaries. The publisher's "Extreme Fear" label covers values from 5 to 25. Query 3 in `outputs/tables/query_03_forward_returns_by_sentiment_bucket.csv` uses the publisher's labels. The sentiment findings use my buckets. The two tables are not interchangeable.

## Overlapping windows inflate apparent significance

A 90-day rolling correlation shares 89 of its 90 days with the next day's reading. The 20-day and 60-day forward returns overlap in the same way. The model's features overlap too. Consecutive rows are not independent observations, so the effective sample is much smaller than the row count. The 117 extreme greed days in `sentiment_forward_returns_summary.csv` are one example. I run no significance tests. If I had, the p-values would be too small.

## One asset over eight years is a small sample of macro regimes

The regime file has 16 periods. Only two of them are HARD_ASSET, and they total 111 days (`query_04_regime_duration_and_count.csv`). The current one is 30 trading days old. The sample contains one pandemic shock and one rate-hiking cycle. I cannot say how the regime rules would behave in a different macro environment.

## Annualised figures for short periods mislead

Annualising a short period scales its average daily return up to a year. The 20-day MIXED period from 2020-12-14 to 2021-01-12 has an annualised return of 2,816.80, which is 281,680%. The arithmetic is correct and the number means nothing. Read the return column of `outputs/tables/regime_summary_statistics.csv` only for periods longer than a few months. The same warning applies to the current 30-day HARD_ASSET period.

## Calendar alignment changes what a day means

I keep only the days Nasdaq traded. Bitcoin's Monday return therefore covers the whole weekend. When I drop weekend returns instead, the latest 90-day Bitcoin-Nasdaq correlation moves from 0.38 to 0.31 (`robustness_weekend_handling.csv`). That is a 0.07 difference from one design choice, and it is larger than some of the gaps to published figures that I explain in `docs/validation.md`.

## The gold series is a choice

My headline gold series is the GLD ETF, because it trades on the same calendar as the panel. Gold futures (`GC=F`) give a different reading. On 2026-08-31 the two differ by 0.06 (0.55 for GLD, 0.49 for `GC=F`, in `validation_comparison.csv`). Published figures do not always say which gold series they use.

## The published figures are secondary sources

I could not locate Grayscale's own report. The Grayscale numbers come from press coverage, and the outlets covering Bitwise's report disagree on some figures. `docs/sources.md` lists each outlet and what I could and could not confirm. My comparison is only as good as those articles.

## The data is one snapshot

The cached pulls end between 2026-07-01 and 2026-09-18, depending on the series. `data/raw/_manifest.json` records the retrieval time, row count and date range of each file. The cache is valid for one UTC day. A run on any later day fetches fresh data, needs a FRED API key, and produces different numbers from the ones in `docs/findings.md`. FRED revises some series, and yfinance adjusts historical prices, so even the overlapping dates can change.

The monthly `M2SL` and weekly `WALCL` series are forward-filled into the daily panel. Their daily values are step functions, and a flag column marks every filled row.

## The classifier is exploratory

It does not beat the persistence baseline (`ml_model_comparison.csv`). It says nothing about Bitcoin's price. `docs/ml-caveats.md` covers the leakage risk from overlapping windows and why accuracy is a weak metric under this class imbalance.

## Software versions

I built and ran everything on Python 3.14.7 with the versions pinned in `requirements.txt`. Other versions of pandas or scikit-learn can change small numerical details. The pipeline asserts that my hand-written correlation matches pandas to within 1e-9.
