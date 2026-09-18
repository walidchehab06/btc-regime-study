# Findings

I report five findings. Each one names the table that holds its numbers and the figure that shows it, and each carries its own caveat. Correlations are rounded to two decimals, which is the precision I trust. Forward returns are log returns, rounded to three decimals. The data runs through 2026-09-17. Nothing here is a trading rule, and I run no significance tests.

## 1. Nasdaq has been Bitcoin's stronger link in most years, and gold leads only at the end of the sample

In 8 of the 9 calendar years, Bitcoin's average 90-day correlation with Nasdaq exceeds its average with gold. The exception is 2019 (gold 0.23, Nasdaq -0.09). Nasdaq peaked in 2022 at 0.57. Gold's yearly average peaked in 2020 at 0.31 and reads 0.29 for 2026 to date, against 0.50 for Nasdaq.

The last reading tells a different story. On 2026-09-17 the 90-day correlation is 0.58 with gold and 0.38 with Nasdaq. The 30-day readings are 0.60 and 0.28. The 90-day correlation with the dollar index is -0.41.

Sources: `outputs/tables/query_01_avg_correlation_by_year.csv`, `outputs/tables/correlation_latest_snapshot.csv`. Figures: `fig01_rolling_correlations_overview.png`, `fig02_window_sensitivity.png`, `fig04_correlation_heatmap.png`.

Caveat: the 2026 gold average (0.29) sits far below the latest reading (0.58), so the rise is recent and a yearly average hides it. Consecutive 90-day readings share 89 of their 90 days, so they are not independent observations.

Three robustness checks leave this picture intact. Dropping weekend returns instead of absorbing them moves the latest 90-day Nasdaq reading from 0.38 to 0.31 and the gold reading from 0.58 to 0.55. Full-period correlations move by 0.02 or less (`robustness_weekend_handling.csv`). Pearson and Spearman differ on average by 0.04 to 0.06 points. They differ by more than 0.10 on 11% to 13% of days. The largest gap is 0.53 for Nasdaq on 2020-03-13, the same week as the March 2020 crash (`robustness_pearson_vs_spearman.csv`). The 30-day and 90-day gold readings have opposite signs on 17% of days, and on 12% for Nasdaq (`robustness_window_30_vs_90.csv`).

## 2. The regime label changed to HARD_ASSET on 2026-08-06, and the change survives every threshold pair I tested

The regime was RISK_ASSET for 213 trading days, from 2025-09-30 to 2026-08-05. It has been HARD_ASSET since 2026-08-06. The earlier HARD_ASSET period ran 81 days, from 2020-08-19 to 2020-12-11. Over the whole sample, the rules and the 15-day persistence filter produce 16 regime periods. Without the filter there are 79 runs, and the label flips on 78 days. With it, the label flips on 15 days.

I re-ran the classification on the full 5-by-5 grid of Nasdaq and gold thresholds. A regime transition falls in 2026 in all 25 cells. The number of regime periods ranges from 13 to 17. The RISK_ASSET share of days ranges from 25% to 46%, driven mostly by the Nasdaq threshold.

Sources: `query_09_regime_timeline.csv`, `query_04_regime_duration_and_count.csv`, `regime_label_stability_before_after.csv`, `sensitivity_grid.csv`. Figures: `fig03_regime_timeline.png`, `fig05_sensitivity_heatmap.png`, `regime_label_stability_before_after.png`.

Caveat: the current HARD_ASSET period is 30 trading days old, twice the 15-day minimum. The sensitivity test only checks that some transition lands in 2026. It does not check that the new label is HARD_ASSET in every cell. The regime labels are rules I wrote, not something observed in the market.

## 3. My correlations land within 0.06 of the published figures, and within 0.02 once I match the instrument

| Published claim | Published | My value | Series | Delta |
|---|---|---|---|---|
| Grayscale, BTC-Nasdaq, 2026-09-02 | 0.33 | 0.36 | `^IXIC` | +0.03 |
| Grayscale, BTC-gold, 2026-09-02 | 0.50 | 0.56 | `GLD` | +0.06 |
| Bitwise, BTC-gold, 2026-08-31 | 0.50 | 0.55 | `GLD` | +0.05 |
| Bitwise, BTC-gold, 2026-08-31 | 0.50 | 0.49 | `GC=F` | -0.01 |
| Bitwise, BTC-Nasdaq, 2026-08-31 | 0.30 | 0.35 | `^IXIC` | +0.05 |
| Bitwise, BTC-Nasdaq, 2026-08-31 | 0.30 | 0.32 | `^NDX` | +0.02 |

Source: `outputs/tables/validation_comparison.csv`. Figure: `fig10_validation_comparison.png`.

Caveat: I could not reach Grayscale's own report. Both Grayscale figures come from press coverage, and neither article states the data vendor or an exact as-of date. The gap to those two figures is real, but I cannot decompose it. Bitwise's figures come from secondary coverage too, and outlets differ on some of them (see `docs/sources.md`).

## 4. Extreme greed days are followed by the largest returns, extreme fear days by roughly zero at 60 days, and dispersion swamps every mean

| Horizon | Bucket | n | Mean | Median | Std dev |
|---|---|---|---|---|---|
| 20 days | Extreme fear | 292 | 0.032 | 0.033 | 0.167 |
| 20 days | Extreme greed | 117 | 0.144 | 0.117 | 0.217 |
| 20 days | Moderate | 1,737 | 0.009 | 0.006 | 0.184 |
| 60 days | Extreme fear | 284 | 0.000 | -0.025 | 0.266 |
| 60 days | Extreme greed | 117 | 0.340 | 0.193 | 0.487 |
| 60 days | Moderate | 1,705 | 0.049 | 0.028 | 0.344 |

The table shows two of the four horizons. The 1-day and 5-day rows are in the same file. Extreme greed has the highest mean at all four horizons. The standard deviation is larger than the mean in every cell of the file.

On whether extremes cluster near regime transitions: extreme greed days sit a mean of 36.2 trading days from the nearest regime boundary, against 46.9 for moderate days. Extreme fear days sit further away, at 62.0. Of 280 extreme fear days that carry a regime label, 189 (67.5%) fall in RISK_ASSET periods.

Sources: `sentiment_forward_returns_summary.csv`, `sentiment_transition_proximity.csv`, `query_10_sentiment_regime_crosstab.csv`. Figures: `fig06_sentiment_overview.png`, `fig07_forward_return_distributions.png`.

Caveat: the 20-day and 60-day windows overlap almost completely from one day to the next. The 117 extreme greed observations amount to far fewer independent periods, and any test I ran would report p-values that are too small. The Fear & Greed Index is a proprietary composite whose construction I cannot verify. Extreme fear has 284 observations at 60 days, not 292, because the last 60 days have no complete forward window.

## 5. Neither model beats predicting that the regime will not change

I predicted the regime label 5 trading days ahead with a multinomial logistic regression and a decision tree of depth 4. I validated both with a walk-forward split of 5 folds, never shuffled. All four methods below ran through the same folds.

| Method | Accuracy | Balanced accuracy | Macro F1 |
|---|---|---|---|
| Persistence baseline | 0.962 | 0.944 | 0.949 |
| Decision tree, depth 4 | 0.841 | 0.733 | 0.722 |
| Logistic regression | 0.676 | 0.563 | 0.559 |
| Majority-class baseline | 0.257 | 0.250 | 0.102 |

Each row pools 1,700 out-of-fold predictions. Sources: `ml_model_comparison.csv`, `ml_per_fold_metrics.csv`, `ml_confusion_matrices.csv`, `ml_class_support.csv`. Figures: `fig08_confusion_matrices.png`, `fig09_decision_tree.png`.

I expected this result. The labels come from a 90-day window and a 15-day persistence filter, so the label 5 days from now is almost always today's label. Persistence is wrong on 64 of 1,700 predictions. By construction, each of those is a day on which the label changes inside the 5-day window. The tree's first split is on the current regime, which is the information persistence already uses. I fixed the tree depth at 4 before I looked at any score and did not tune anything afterwards.

The two weaker models fail in specific ways. Logistic regression sends 234 of 870 true RISK_ASSET days and 146 of 432 true MIXED days to IDIOSYNCRATIC. The tree sends 131 true RISK_ASSET days and 78 true HARD_ASSET days to MIXED. HARD_ASSET has 108 target days, the smallest class in the file.

Caveat: five folds, one history and two simple models. Overlapping feature windows mean the effective sample is much smaller than 1,700 (see `docs/ml-caveats.md`). The tree's full-history fit in figure 9 is for illustration and is never scored.
