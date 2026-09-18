# ML caveats

Read these three points before you read any number in `outputs/tables/ml_model_comparison.csv` or in finding 5 of `docs/findings.md`.

## 1. Overlapping windows mean the folds are not independent

Every feature in `src/model.py:CONTINUOUS_FEATURE_COLUMNS` is a rolling or `.diff()` calculation over a trailing window of 20 or 90 trading days. The feature row for one date and the row for the next date share almost all of their underlying days. `realized_vol_20` on Tuesday and on Wednesday use 19 of the same 20 daily returns. This is the overlapping-window problem that `docs/methodology.md` describes for forward returns, showing up on the feature side.

`TimeSeriesSplit(gap=config.ML_TIMESERIES_GAP_DAYS)` prevents one narrow problem. It stops a training row's target, which is dated `ML_TARGET_HORIZON_DAYS` trading days ahead of that row, from falling inside the following test fold. It does not make adjacent rows independent. Rows inside a fold, and the folds themselves, still share most of their raw data.

The walk-forward metrics are therefore a fair comparison between methods, because every method sees the same folds, gap and features. They are not precise estimates. The effective sample behind each number is much smaller than the 2,045 rows in `ml_features_daily.csv`. I treat the metrics as directional and attach no standard error to them.

## 2. Why accuracy is a weak metric here

Regime labels are persistent by construction. They come from a 90-day rolling window and a 15-day minimum-persistence filter (`src/regimes.py`). The classes are also imbalanced. HARD_ASSET has 108 target days and RISK_ASSET has 870 (`ml_class_support.csv`). Under those conditions, both baselines can score well with no predictive skill at all.

Persistence wins on almost every row where the target class equals the current class. That is most rows, because regimes rarely flip. Majority-class wins whenever the training window is dominated by one label, which the imbalance makes likely. In this study its accuracy is only 0.257, because the expanding training window's most common label, IDIOSYNCRATIC, is wrong for most of the test days.

This is why my build specification requires balanced accuracy, macro F1, a confusion matrix and class support beside plain accuracy for every method, baselines included. A single accuracy number from a persistent, imbalanced target is easy to read as skill that is not there.

## 3. The result is exploratory, not actionable

This project is descriptive, not predictive. It produces no trading signals, price forecasts or strategy backtests. I built the classifier to ask whether any signal in these features predicts the regime label days ahead, beyond assuming it stays the same. I did not build it to trade on. Two more reasons the result is not actionable, even if a model beat persistence on some metric in some fold:

The target and several features come from the same calculation. The 30-day and 90-day correlations are features, and the regime target is built from the 90-day correlations. Some of any relationship a model finds is closer to "the target is mechanically smooth" than to "the features forecast a real shift".

The evidence is thin. It is one held-out history, five folds and two simple models. That is nowhere near enough to conclude that a tradable edge exists, even in the best case. Neither model beat persistence, and `docs/findings.md` says so in finding 5.
