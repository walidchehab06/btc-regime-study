# Findings

This file collects the headline result from each analytical phase of the
study, in the order BUILD-SPEC-bitcoin-regime-study.md section 12 builds
them. Only Phase 8 is written up here so far -- earlier phases' findings
currently live in `docs/methodology.md` and `docs/validation.md`; this
file will gain their headlines as the write-up phase catches up.

## Phase 8 — the classifier does not beat the persistence baseline (section 6.7)

**Headline: neither model beats the persistence baseline, and that is the
expected, correct result.** Predicting "the regime 5 trading days from now
is whatever it is today" gets 96.2% out-of-fold accuracy. The decision
tree reaches 84.1%; multinomial logistic regression reaches 67.6%. Both
are worse than doing nothing.

| Method | Accuracy | Balanced accuracy | Macro F1 | n (pooled out-of-fold) |
|---|---|---|---|---|
| Persistence baseline | 0.962 | 0.944 | 0.949 | 1,700 |
| Majority-class baseline | 0.257 | 0.250 | 0.102 | 1,700 |
| Logistic regression | 0.676 | 0.563 | 0.559 | 1,700 |
| Decision tree (max depth 4) | 0.841 | 0.733 | 0.722 | 1,700 |

Source: `outputs/tables/ml_model_comparison.csv`, computed on every
method's predictions pooled across all 5 `TimeSeriesSplit` walk-forward
folds (`gap=5` trading days -- see `docs/decisions-log.md`). Per-fold
detail: `outputs/tables/ml_per_fold_metrics.csv`. Confusion matrices:
`outputs/tables/ml_confusion_matrices.csv` and figure 8. Class support
(target days per regime, full 2,045-row dataset): RISK_ASSET 870,
IDIOSYNCRATIC 635, MIXED 432, HARD_ASSET 108 --
`outputs/tables/ml_class_support.csv`.

### Why this is the expected result, not a failure

Regime labels are built from a 90-day rolling correlation and then run
through a 15-day minimum-persistence filter (`src/regimes.py`). By
construction, the label 5 trading days from now is, in the overwhelming
majority of cases, identical to today's label -- only 16 regime periods
exist across the entire ~8.5-year study, an average length measured in
months, not days. "Predict no change" is therefore close to the best
possible strategy for this specific target, independent of any real
market signal. Section 6.7 states this plainly in advance: a student who
explains why their model failed to beat a naive baseline, given exactly
how the target was constructed, demonstrates more competence than one who
reports a high accuracy number on what turns out to be a mechanically
easy target. No parameter was tuned after seeing this comparison --
`config.ML_TREE_MAX_DEPTH` was fixed at 4 before evaluation, per
`docs/decisions-log.md`.

### What the models get partly right, and where they fail

The decision tree's illustrative full-history fit (figure 9) is
informative about *why* it underperforms persistence even though it
scores respectably in isolation: its very first split is
`regime_RISK_ASSET <= 0.5`, i.e. the current regime one-hot feature --
the tree has effectively rediscovered that "what is the regime right
now" is the single most useful piece of information available, which is
exactly what the persistence baseline uses directly and perfectly, with
no fitting required. The tree adds a small amount of value by also
splitting on the 90-day BTC-Nasdaq, BTC-gold, and BTC-DXY correlations
beneath that, but every additional split is working with a strictly
weaker signal than the one the persistence baseline already has for
free.

The confusion matrices (figure 8) show where each method actually loses
ground:
- **Persistence** is near-diagonal everywhere; its only material
  mistakes are days where a genuine regime transition happens within the
  5-day window, which it cannot see coming.
- **Majority class** always predicts IDIOSYNCRATIC (the expanding
  training window's most common label in every fold) and gets every
  RISK_ASSET, HARD_ASSET, and MIXED day wrong by construction -- exactly
  the class-imbalance failure mode `docs/ml-caveats.md` describes.
- **Logistic regression** confuses RISK_ASSET and MIXED with
  IDIOSYNCRATIC heavily (234 of 870 true RISK_ASSET days and 146 of 432
  true MIXED days predicted IDIOSYNCRATIC) and essentially never predicts
  HARD_ASSET correctly relative to its true frequency.
- **The decision tree** does better on the majority classes but
  systematically confuses RISK_ASSET and HARD_ASSET with MIXED (131 and
  78 days respectively), the class its splits are least able to isolate
  cleanly at depth 4.

### Scope of this result

This comparison is walk-forward (never shuffled -- see
`docs/decisions-log.md` for why a shuffled split would be invalid for an
autocorrelated, persistence-filtered target) and pools five
non-overlapping test folds spanning 2019-10-31 through 2026-09-10. It is
still one held-out history, five folds, and two simple models -- see
`docs/ml-caveats.md` for the overlapping-feature-window caveat and why
this result, even where a model does relatively well (e.g. the decision
tree's 0.841 accuracy), should be read as exploratory, not as evidence of
a tradable signal. Per `CLAUDE.md`, this project produces no trading
signals, price forecasts, or strategy backtests, and this section is not
an exception.
