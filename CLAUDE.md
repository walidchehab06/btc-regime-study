# Project context for Claude Code

This repository is a Bitcoin cross-asset regime study. The complete build
specification is in docs/BUILD-SPEC-bitcoin-regime-study.md. Read it fully
at the start of every session before writing any code.

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

Phase 6 (validation, `src/validation.py`, figure 10) completed earlier and
is not re-summarized here — see docs/decisions-log.md and
docs/validation.md. Phase 8 (the ML component) not started.
