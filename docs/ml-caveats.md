# ML caveats (BUILD-SPEC section 6.7)

Three things worth understanding clearly before reading any number out of
`outputs/tables/ml_model_comparison.csv` or `docs/findings.md`'s Phase 8
section.

## 1. Overlapping windows mean the folds aren't independent

Every feature in `src/model.py:CONTINUOUS_FEATURE_COLUMNS` is a rolling or
`.diff()` calculation over a trailing window (20 or 90 trading days). The
feature row for one date and the feature row for the next date share
almost all of their underlying days -- `realized_vol_20` on Tuesday and
`realized_vol_20` on Wednesday are computed from 19 of the same 20 daily
returns. This is exactly the overlapping-window problem
`docs/methodology.md`'s sentiment section already documents for forward
returns, showing up here on the feature side instead.

`TimeSeriesSplit(gap=config.ML_TIMESERIES_GAP_DAYS)` prevents a very
specific, narrower problem: it stops a training row's *target* (which is
dated `ML_TARGET_HORIZON_DAYS` trading days ahead of that row) from
falling inside the following test fold. It does **not** make adjacent
rows independent observations of anything -- the rows inside a single
fold, and the folds themselves, still share most of their underlying raw
data. The practical consequence: the walk-forward metrics in
`ml_model_comparison.csv` are a fair *comparison* between methods (every
method sees the same folds, the same gap, the same features), but the
*effective* sample size behind each number is much smaller than the row
count in `ml_features_daily.csv` suggests. Treat the metrics as directional,
not as precise estimates with a meaningful standard error.

## 2. Why accuracy is a weak metric here

Regime labels are persistent by construction (`src/regimes.py`'s 90-day
rolling window and 15-day minimum-persistence filter), and the classes
are imbalanced -- some regimes hold for months, others rarely occur. Under
those conditions, both required baselines can already score well without
any genuine predictive skill:

- **Persistence** wins almost automatically whenever the target class is
  unchanged from the current class, which is most rows, simply because
  regimes don't flip often.
- **Majority class** wins whenever the training window happens to be
  dominated by one label, which class imbalance makes likely.

This is exactly why section 6.7 requires balanced accuracy, macro F1, a
confusion matrix, and class support alongside plain accuracy for every
method, baselines included -- a single accuracy number from an imbalanced,
persistent target is easy to misread as skill that isn't there.

## 3. This is exploratory, not actionable

Per `CLAUDE.md`'s non-negotiables, this project is descriptive, not
predictive: no trading signals, no price forecasts, no strategy backtests.
Phase 8's classifier exists to ask "does *any* signal in these features
predict the regime label days in advance, beyond just assuming it stays
the same," not to produce something meant to be traded on. Two further
reasons this result specifically shouldn't be read as actionable, even if
a model does edge out the persistence baseline on some metric in some
fold:

- The regime *target* and several of the model's *features* (the 30- and
  90-day correlations) are both derived from the same underlying rolling
  correlation calculation `src/regimes.py` uses to build the target in
  the first place. Some of whatever predictive relationship the model
  finds is closer to "the target is mechanically smooth" than "the
  features forecast a genuine shift."
- One held-out history, five folds, two simple models. That is nowhere
  near enough evidence to conclude a real, tradable edge exists even in
  the best case -- see the honesty requirement in
  `docs/BUILD-SPEC-bitcoin-regime-study.md` section 6.7 and the resulting
  headline in `docs/findings.md`.
