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
Phase 5 — complete. `src/regimes.py` built: rule-based classification on
the 90-day Pearson `BTC_NASDAQ`/`BTC_GOLD` correlations
(`classify_regime`), the 15-trading-day persistence filter
(`apply_persistence_filter`, merges a short run into the *preceding*
regime — owner-confirmed, see docs/decisions-log.md), the regime timeline
and per-day regime tables (`build_regime_periods`,
`build_regimes_daily`), per-regime statistics (annualized return/
volatility, max drawdown, avg Fear & Greed — new hand-written functions in
`src/core_math.py`), and the mandatory section 6.5 sensitivity grid (25
threshold combinations, `run_sensitivity_grid`). `src/charts.py` gained
figure 3 (regime timeline) and figure 5 (sensitivity heatmap); figure 1
now shades regime bands. Chart generation moved out of Phase 4 and into
its own `run_charts()` step, run after Phase 5, since figures 1/3/5 all
need `regime_periods` (see docs/decisions-log.md). `python -m src.run_all`
now runs Phase 5 after Phase 4: 2,078 days classified, 16 regime periods
after filtering, sensitivity grid confirms the 2026 regime shift survives
all 25 threshold combinations. Query 9 (regime timeline) added to
sql/analysis_queries.sql; queries 4, 6, and 9 now return non-vacuous
results. `pytest tests/` passes (43/43). Phase 6 (validation) not started.
