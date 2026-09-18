# Project context for Claude Code

This repository is a Bitcoin cross-asset regime study. A build specification
directed its construction but is not included in the public repo. For the
analytical choices and the reasons behind them, read docs/methodology.md
and docs/decisions-log.md.

## Non-negotiables
- Never fabricate data, numbers, or citations. If a data source fails, stop and
  report the failure. Do not generate placeholder or synthetic data.
- This project is descriptive, not predictive. No trading signals, no price
  forecasts, no strategy backtests.
- Never shuffle time-series data in cross-validation. Walk-forward only.
- Readability over cleverness. The repo owner is a Python beginner who must be
  able to explain every line in a job interview.
- All tunable parameters live in src/config.py. No magic numbers elsewhere.
- Log every non-obvious decision to docs/decisions-log.md.
- Print row counts before and after every merge.

## Environment
- Windows, PowerShell, Python 3.11+, virtual environment at .venv
- Activate with: .venv\Scripts\Activate.ps1
- Secrets are in .env (FRED_API_KEY). Never read it aloud, never commit it.

## Commands
- Full pipeline: python -m src.run_all (Windows, no `make` installed — see
  docs/decisions-log.md)
- Tests: pytest tests/

## Current phase
Build complete — Phase 9 done, moving to owner's writeup and publishing pass.

Phase 9 summary: this was the last build phase. All nine files under
docs/ exist (methodology, data-dictionary, validation, findings,
limitations, ml-caveats, sources, future-work, decisions-log), written in
first person to section 10's rules. docs/findings.md holds five findings,
and every number in it traces to a file in outputs/tables/. README.md is
under 600 words. requirements.txt pins all 45 installed packages (9 direct,
36 transitive). New `src/robustness.py` (run by `run_all` as Phase 9, after
Phase 8) writes four tables: `robustness_weekend_handling.csv`,
`robustness_pearson_vs_spearman.csv`, `robustness_window_30_vs_90.csv`,
`correlation_latest_snapshot.csv`. Figure 5 got a caption and contrast fix
and its pass/fail marks became "yes"/"no". `pytest tests/` passes (63/63).
Verified in a clean copy with a fresh venv: `python -m src.run_all` used
the cache and reproduced all 37 tables and figures byte for byte. The fetch
cache expires after one UTC day, so a run after 2026-09-18 re-fetches, needs
a FRED key, and gives different numbers (see docs/limitations.md and
docs/future-work.md). Any further work is maintenance, not a new phase.

Phase 8 — complete. `src/model.py` built: the section 6.7 classifier
predicting the regime label 5 trading days ahead (`config.ML_TARGET_HORIZON_DAYS`),
multinomial logistic regression and a decision tree capped at
`config.ML_TREE_MAX_DEPTH` (4, fixed before evaluation, not tuned — see
docs/decisions-log.md), features built only from trailing/current-date
information (`compute_technical_features`, `build_feature_matrix`): 30-
and 90-day Pearson correlations with Nasdaq/gold/DXY, 20-day realized BTC
volatility, 20-day BTC momentum, 20-day DXY and real-yield change, F&G
level and its 14-day change, and the current regime label one-hot
encoded. Validated with `TimeSeriesSplit(n_splits=5, gap=5)`
(`run_walk_forward_evaluation`) — never shuffled, see docs/decisions-log.md
for why. Both required baselines (persistence, majority-class, the
latter recomputed per fold from that fold's own training labels) run
through the identical walk-forward loop alongside both models. Accuracy,
balanced accuracy, macro F1, confusion matrix, and class support reported
for all four methods (`build_model_comparison_table`,
`build_confusion_matrices`, `build_class_support_table`). Result matches
section 6.7's expected headline: persistence (accuracy 0.962) beats both
the decision tree (0.841) and logistic regression (0.676); no parameter
was tuned after seeing this, and docs/findings.md states it plainly as
the headline, per section 6.7's honesty requirement.
`src/charts.py` gained figure 8 (confusion matrices, all four methods)
and figure 9 (the depth-4 tree, fit on the full history for illustration
only, never scored — see docs/decisions-log.md), both rendered from
`src/model.py:main()` directly rather than `charts.main()`, same
reasoning as Phase 5's before/after diagnostic chart. `src/run_all.py`
now runs Phase 8 after Phase 7 and before `run_charts()`. New
docs/ml-caveats.md covers overlapping-window leakage risk, why accuracy
is weak under this target's class imbalance, and why the result is
exploratory only. `pytest tests/` passes (57/57, including the new
`tests/test_model.py`).

Phase 7 — complete. `src/sentiment.py` built: sentiment bucketing
(`assign_sentiment_bucket`, `EXTREME_FEAR` <=20 / `EXTREME_GREED` >=80 /
`MODERATE`, computed from `fng_value` directly — deliberately not the
same boundaries as the vendor's own `fng_label`, see
docs/decisions-log.md), forward log returns at 1/5/20/60 trading days
(`compute_forward_log_returns`), and the n/mean/median/std summary table
required by section 6.6 (`build_forward_returns_summary`). Also the
section 6.6 "do extremes cluster near transitions" question, answered two
ways: a SQL cross-tab of sentiment bucket x regime label (query 10 in
sql/analysis_queries.sql) and a Python distance-to-nearest-transition
comparison (`compute_days_to_nearest_transition`,
`build_transition_proximity_summary`). `src/charts.py` gained figure 6
(Bitcoin price with Fear & Greed overlay, extreme bands shaded) and
figure 7 (forward-return box plots by bucket, one panel per horizon, n
annotated on every box). `src/run_all.py` now runs Phase 7 after Phase 6
and before `run_charts()`. The overlapping-window problem (20- and 60-day
forward returns share nearly all their underlying days from one date to
the next) is documented explicitly in docs/methodology.md; no
significance test is run anywhere in this phase, per section 6.6's
instruction. `pytest tests/` passes (51/51, including the new
`tests/test_sentiment.py`).

Phases 1-6 (through validation, `src/validation.py`, figure 10) completed
earlier and are not re-summarized here — see docs/decisions-log.md and
docs/validation.md.
