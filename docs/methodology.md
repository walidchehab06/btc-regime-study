# Methodology

This document explains, in plain English, every analytical choice in the pipeline. Each choice is deliberate. Where I had to decide something the spec left open, the reasoning is in `docs/decisions-log.md`.

## Calendar alignment

Bitcoin trades every day of the year. Nasdaq-listed equities, gold futures and the dollar index trade only when their exchanges are open. Correlating series that do not share a calendar either creates phantom gaps or silently misaligns dates, so I need a rule.

**The rule: I restrict the panel to the days Nasdaq (`^IXIC`) traded.** Every other series is aligned onto that set of dates. A date Nasdaq did not trade is dropped for every series, including Bitcoin.

The consequence is that Bitcoin's Monday return is not a one-day return. Bitcoin moved on Saturday and Sunday, but those dates are not in the panel, so Monday's log return is `ln(close_Monday / close_Friday)`. It absorbs the weekend into one multi-day figure. I made this choice explicitly instead of leaving it as a side effect of a merge.

**Robustness check.** `panel_daily_alt_weekend.parquet` is an alternative panel that computes Bitcoin's log return the other way round. It computes the return on Bitcoin's own daily calendar first, so Saturday and Sunday each get a one-day return, and only then aligns onto the Nasdaq calendar. Monday's row then holds only the Sunday-to-Monday return, and the weekend return is dropped. Every other column is identical between the two panels, so any difference downstream comes from this one choice. The two methods disagree on 474 of 2,168 days, about 22%. Of those, 407 are Mondays. The rest fall on the day after a Nasdaq holiday.

The effect on the headline correlations is small at the full-period level and visible at the latest date. Full-period correlations move by 0.02 or less for all three pairs. The latest 90-day Nasdaq correlation moves from 0.38 to 0.31, and the gold correlation from 0.58 to 0.55. The regime rules use 90-day readings, so a 0.07 shift could matter at a threshold. I use the absorbed version as the headline because it counts all of Bitcoin's price movement. The numbers are in `outputs/tables/robustness_weekend_handling.csv`.

**Timezones.** `yfinance` returns UTC-labelled daily bars and alternative.me returns Unix timestamps. I convert both to UTC calendar dates before merging, so a "day" means the same thing in every source.

## Returns, not price levels

Every correlation in this project uses daily logarithmic returns, `r_t = ln(P_t / P_{t-1})`. I never correlate raw prices.

Two trending price series look correlated because both drift, whether or not they move together on any given day. Statisticians call such series non-stationary. Their statistical properties change over time. Log returns are approximately stationary, and they measure what I care about: does the asset move on the same days as the other one. Correlating price levels is a common mistake in informal crypto analysis, and I name it here so nobody has to wonder whether I made it.

## Forward-filling the monthly and weekly macro series

`M2SL` (M2 money supply) is published monthly and `WALCL` (Fed balance sheet) weekly. The daily panel needs a value for every row, so between releases I carry the last published value forward.

This turns data that changes once a month or once a week into something that looks daily. Plotted, it is a staircase. A rolling correlation against a forward-filled M2 series would be driven by a handful of distinct M2 readings, not by independent daily observations. The panel carries an `is_forward_filled_*` boolean next to every forward-filled value. It is `True` on any date that is not one of the series' own release dates. Before a series' first release there is nothing to carry forward, so the value stays `NaN`. No finding in this project depends on `M2SL` or `WALCL`.

## Two calendar mismatches

Building the panel exposed two gaps. Neither is a data-quality problem.

**Daily FRED series on bond-market holidays.** `DFII10`, `DTWEXBGS` and `T10Y2Y` are `NaN` on Columbus Day and Veterans Day every year, and on a few other bond-market-only closures. The Treasury market observes holidays that Nasdaq does not. I leave these as `NaN`. The data-integrity assertions tolerate up to 5% missing in a daily FRED column (`FRED_DAILY_MAX_NAN_FRACTION`). See `docs/decisions-log.md`.

**One missing sentiment day.** The Fear & Greed Index has no value for 2018-04-16. That is a gap in the source's own history, not a holiday. I leave it as `NaN`. Sentiment is not on the spec's forward-fill list, and extending the list for one row was not worth the assumption.

## Rolling correlations

I measure Bitcoin's relationship to Nasdaq, gold and the dollar index with a rolling Pearson correlation of daily log returns. I recompute the correlation on a moving window of trading days, so it can change over time instead of collapsing the study into one number. I compute two windows in parallel. The 30-day window reacts quickly and is noisy. The 90-day window is smoother, and it matches most published institutional figures (`docs/sources.md`). Neither window is allowed a partial start. The first 90-day value needs 90 days of returns.

The 30-day and 90-day windows give visibly different answers. Over the days where both exist, they have opposite signs on 12% of days for Nasdaq, 17% for gold and 23% for the dollar index. I chose 90 days because it matches the published figures and reacts less to single weeks. The table is `outputs/tables/robustness_window_30_vs_90.csv` and figure 2 shows the effect.

**Two independent implementations of the 90-day Pearson correlation.** I compute the headline window twice. One version calls pandas' `.rolling().corr()`. The other is a function I wrote in `src/core_math.py`, which computes the covariance and the two standard deviations from the definition, `corr(x, y) = cov(x, y) / (std(x) * std(y))`. The pipeline asserts that the two agree to within `1e-9` on every date. Pandas is not unreliable. I need to be able to explain what a correlation coefficient measures, and writing it by hand is how I learned that.

**Spearman as a robustness check, 90-day window only.** Pearson correlation is sensitive to outliers, and Bitcoin has extreme days. Spearman correlation ranks the values first. `rolling_spearman()` in `src/correlations.py` ranks the two series within each 90-day window separately, because a value's rank depends on what else is in the window. It then calls the same hand-written Pearson function on the ranks. Spearman is by definition the Pearson correlation of ranks, and this avoids adding `scipy` for one function. A test checks it on `y = x**3`. That series is perfectly predictable from `x` but not linear, so Pearson is high but below 1 while Spearman is exactly 1.

The two methods differ by 0.04 to 0.06 on average. They differ by more than 0.10 on 11% to 13% of days, and I count those as notable disagreements. The largest gap is 0.53, for Nasdaq on 2020-03-13. At the latest date the two agree closely for Nasdaq (0.38 and 0.38) and gold (0.58 and 0.57). For the dollar index they differ by 0.06 (-0.41 and -0.35). The numbers are in `outputs/tables/robustness_pearson_vs_spearman.csv`.

**Three headline pairs, and which gold and dollar series.** The pairs are `BTC_NASDAQ` (Bitcoin vs `^IXIC`), `BTC_GOLD` and `BTC_DXY` (Bitcoin vs `DX-Y.NYB`, the ticker I mean by "DXY"). For gold, the headline series is `GLD`, the ETF, not `GC=F` futures. `GLD` trades on the calendar the panel is anchored to. `GC=F` trades different hours, which would add a second calendar mismatch on top of Bitcoin's. `GC=F` is the section 5.1 robustness check, computed in the validation step under its own pair label. The spec says to decide the headline gold series deliberately, so I chose `GLD` on purpose and logged the reasoning in `docs/decisions-log.md`.

## Regime classification

I classify every trading day into one of four regimes using rules on that day's 90-day Pearson correlations. I do not use a clustering algorithm. Rules make the thresholds visible and easy to stress-test.

| Regime | Condition |
|---|---|
| `RISK_ASSET` | corr(BTC, Nasdaq) >= 0.40 and corr(BTC, Nasdaq) > corr(BTC, Gold) |
| `HARD_ASSET` | corr(BTC, Gold) >= 0.35 and corr(BTC, Gold) > corr(BTC, Nasdaq) |
| `IDIOSYNCRATIC` | both correlations below 0.25 in absolute value |
| `MIXED` | anything not matching the above |

These thresholds are a starting proposal, not a fitted result. The sensitivity grid below tests whether they matter.

**The persistence filter.** Applying the rule to every day independently produces labels that flicker. The raw labels form 79 runs of consecutive identical labels, with a median length of 7 trading days, and 63% of runs are shorter than 15 days. A regime that changes every week is noise near a threshold. The filter keeps a run as its own regime only if it lasts at least 15 consecutive trading days. Shorter runs merge into the surrounding regime.

The spec did not say which regime absorbs a short run that sits between two different regimes. I merge it into the preceding regime, because a brief blip inside an established regime should not rewrite what came before. A short run at the very start of the series has no preceding regime, so it takes the label of the regime that follows. A merge can make a run long enough to swallow its own short neighbour, so I repeat the merge until every surviving run is at least 15 days.

The filter's effect, measured:

| | Runs | Median run length | Day-to-day label changes |
|---|---|---|---|
| Raw | 79 | 7 trading days | 78 (3.8% of transitions) |
| Filtered | 16 | 102 trading days | 15 (0.7% of transitions) |

The filter cuts the flip rate about fivefold and leaves 16 periods long enough to describe. `outputs/figures/regime_label_stability_before_after.png` shows the difference, and the counts are in `outputs/tables/regime_label_stability_before_after.csv`.

**Outputs.** The filtered periods form the regime timeline (`outputs/tables/query_09_regime_timeline.csv`, figure 3). For each period, `outputs/tables/regime_summary_statistics.csv` reports Bitcoin's annualised return, annualised volatility, maximum drawdown and average Fear & Greed level. The functions are `annualized_return()`, `annualized_volatility()` and `max_drawdown()` in `src/core_math.py`.

Annualised returns on short periods mislead. The formula scales a period's average daily log return up to a full year. The 20-day MIXED period from 2020-12-14 to 2021-01-12 had an average Fear & Greed reading of 91.7. It annualises to 2,816.80 in the table, which is 281,680%. The number follows from the formula and means nothing as a yearly estimate. The 300-day RISK_ASSET period from 2022-01-11 to 2023-03-22 annualises to -30.1%, and that number is more informative. I read the return column only for periods longer than two or three months. See `docs/limitations.md`.

## Sensitivity analysis

Any threshold rule invites the question "why those numbers". I re-ran the classification and the persistence filter for every combination of the Nasdaq threshold in {0.30, 0.35, 0.40, 0.45, 0.50} and the gold threshold in {0.25, 0.30, 0.35, 0.40, 0.45}. That is 25 combinations (`run_sensitivity_grid()` in `src/regimes.py`). For each, I recorded the number of regime periods, the share of days in each regime, and whether a regime transition still falls in calendar year 2026. At the baseline thresholds, the last transition is on 2026-08-06, when RISK_ASSET gives way to HARD_ASSET.

A transition falls in 2026 in all 25 combinations. The number of regime periods ranges from 13 to 17, against 16 at the baseline. The RISK_ASSET share of days ranges from about 25% to 46%. The Nasdaq threshold drives most of that range, and figure 5 shows a stronger gradient left to right than top to bottom.

The test is loose. It checks that some transition lands in 2026. It does not check that the new label is HARD_ASSET in every combination. I state the result as a survival of the timing of the change, not of the label.

## Sentiment analysis

**Buckets.** Each day gets one of three buckets from the Fear & Greed value alone: `EXTREME_FEAR` (value 20 or below), `EXTREME_GREED` (80 or above) and `MODERATE` (in between). The function is `assign_sentiment_bucket()` in `src/sentiment.py`. These are the bands the spec gives as the publisher's conventional extremes. They are not the same as `fng_label`, the five-category label alternative.me stores next to each value, which query 3 uses. In the panel data, alternative.me's "Extreme Fear" covers values from 5 to 25 and "Extreme Greed" covers 76 to 95. Using `fng_label` here would have applied a different threshold from the one I meant to test. Of 2,167 days with a reading, 292 (13.5%) are `EXTREME_FEAR` and 117 (5.4%) are `EXTREME_GREED`.

**Forward returns.** For each horizon in {1, 5, 20, 60} trading days, the forward log return at day *t* is the sum of Bitcoin's log returns over days *t*+1 to *t*+horizon. I compute it in pandas (`compute_forward_log_returns()`), not in SQL, because the spec requires the median as well as the mean and SQLite has no median function. The summary has n, mean, median and standard deviation for every horizon and bucket. It is in `outputs/tables/sentiment_forward_returns_summary.csv`, and figure 7 plots it. The results are in `docs/findings.md`.

**The overlapping-window problem.** I compute the 20-day and 60-day forward returns for every trading day. The window starting tomorrow shares all but one daily return with the window starting today. Consecutive rows of `outputs/tables/sentiment_forward_returns_daily.csv` are therefore not independent, even though the table has one row per day. The 117 extreme greed observations at 60 days represent far fewer than 117 independent quarters. A naive test would make any pattern look more significant than it is. I run no significance test, as the spec instructs, and none should be inferred from the descriptive statistics.

**Sentiment against regime.** Query 10 cross-tabulates sentiment bucket against regime label (`outputs/tables/query_10_sentiment_regime_crosstab.csv`). Of 280 extreme fear days that carry a regime label, 189 (67.5%) fall in RISK_ASSET periods. Extreme greed days spread across all four regimes: 28 HARD_ASSET, 35 IDIOSYNCRATIC, 34 MIXED and 20 RISK_ASSET.

To ask whether extremes cluster near regime transitions, `compute_days_to_nearest_transition()` measures each day's distance in trading days to the nearest boundary of its own regime period. `outputs/tables/sentiment_transition_proximity.csv` compares that distance across buckets. Extreme fear days sit further from transitions (mean 62.0 days, median 63.0, n=280) than moderate days (mean 46.9, median 38.0, n=1,681). Extreme greed days sit closer (mean 36.2, median 22.0, n=117). These are differences in the sample. I did not test them, for the reason above.

## The classifier

The model is small on purpose. It predicts the regime label 5 trading days ahead (`ML_TARGET_HORIZON_DAYS`) using two models the spec allows: a multinomial logistic regression and a decision tree with `max_depth` fixed at 4. I fixed the depth before I looked at any result. Choosing it by test score would be the tuning the spec forbids.

**Features.** Every feature uses only information available on the prediction date. The list is the 30-day and 90-day Pearson correlations with Nasdaq, gold and the dollar index, 20-day realised Bitcoin volatility, 20-day Bitcoin momentum, the 20-day change in the dollar index (`DX-Y.NYB`) and in the 10-year real yield (`DFII10`), the Fear & Greed level and its 14-day change, and the current regime label one-hot encoded. All windows look backwards. Rows with a missing feature in the warm-up period are dropped, which leaves 2,045 rows (`outputs/tables/ml_features_daily.csv`). A test checks that no missing value reaches the model.

**Validation.** I use `TimeSeriesSplit` with 5 splits and a gap of 5 trading days, which equals the target horizon. Each fold trains on everything before its test block and tests on the next block of 340 days. The gap stops a training row's target, which is dated 5 days ahead, from falling inside the test block. Feature scaling for the logistic regression happens inside a pipeline, so it is fitted on training data only.

I never shuffle. A shuffled split lets the model train on days after the ones it is tested on. Regime labels are highly autocorrelated, so a test day's neighbours on both sides sit in the training set and the model can copy them. That produces impressive and meaningless scores.

**Baselines.** Both run through the same folds as the models. Persistence predicts that the regime in 5 days equals today's. Majority-class predicts the most common label in that fold's own training window, recomputed per fold.

**Scoring.** I report accuracy, balanced accuracy and macro F1, plus confusion matrices and class support, because the classes are imbalanced. The metrics pool the predictions from all five folds. Per-fold numbers are in `outputs/tables/ml_per_fold_metrics.csv`. The result and the reason for it are in `docs/findings.md` and `docs/ml-caveats.md`.

Figure 9 fits the tree on the full history so that it can be drawn and read. That fit is for illustration and I never score it.
