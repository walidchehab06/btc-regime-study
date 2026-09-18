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
Phase 4 — complete. `src/core_math.py` (hand-written Pearson),
`src/correlations.py` (pandas + hand-written 90-day Pearson, 30-day
Pearson, 90-day Spearman, all three BTC pairs), and `src/charts.py`
(figures 1, 2, 4) built. `python -m src.run_all` now runs Phase
4 after Phase 3, loading `rolling_correlations` and
`rolling_correlations_recomputed_check`, then exports all eight analysis
queries (query 8 added for the correlation reconciliation) to
outputs/tables/. Queries 7 and 8 both pass (0 mismatches). Headline
`BTC_GOLD` pair uses GLD, not GC=F (owner's choice, see
docs/decisions-log.md). Phase 5 (regimes) not started.
