# Decisions log

Format: date, decision, alternatives considered, reason, whether the owner
was consulted. Per BUILD-SPEC-bitcoin-regime-study.md section 13, this file
also carries one-line pointers to concepts the owner is currently learning,
rather than turning code comments into a tutorial.

---

**2026-09-18 — `src/run_all.py` as the single pipeline entry point, no Makefile**
Alternatives considered: a `Makefile` (BUILD-SPEC section 7's default), a
`run.sh` shell script.
Reason: development is on Windows without `make` installed. A Python entry
point run as `python -m src.run_all` needs no extra tooling and works the
same in PowerShell as anywhere else.
Owner consulted: yes, explicitly requested.

**2026-09-18 — Raw cache files saved as CSV, not Parquet**
Alternatives considered: Parquet (BUILD-SPEC section 5.4 allows either).
Reason: CSV is readable by eye in a text editor, which matters for a
beginner debugging a failed or malformed pull. Parquet is used from Phase 2
onward for the processed panel, where file size and dtype fidelity start to
matter more than eyeballing.
Owner consulted: no — implementation detail already left open by the spec,
decided per section 13's "do not ask about implementation detail already
specified here."

**2026-09-18 — `src/manifest.py` added as a shared helper module**
Alternatives considered: duplicating manifest read/write/cache-check logic
inside each of `fetch_market.py`, `fetch_fred.py`, and `fetch_sentiment.py`.
Reason: all three fetch modules need to record the same provenance fields
(BUILD-SPEC section 5.4) and apply the same same-day caching rule; one
shared module means that logic is tested and fixed in one place. Not listed
in BUILD-SPEC section 7's repo tree, but adding small internal helper
modules is an implementation detail, not a scope change.
Owner consulted: no.

**2026-09-18 — `pyarrow` added to requirements.txt in Phase 1**
Alternatives considered: adding it only when Phase 2 first writes
`panel_daily.parquet`.
Reason: it's a direct dependency for the Parquet output the repo structure
(BUILD-SPEC section 7) already commits to, and pinning it alongside the
rest of the stack now avoids a mid-project requirements.txt churn. Not
named explicitly in section 11's package list, which is otherwise treated
as the ceiling on dependencies ("nothing else without asking") — flagged
here rather than silently added.
Owner consulted: no.

**2026-09-18 — Phase 1 (data acquisition) signed off as complete**
Alternatives considered: n/a — this is a phase closeout, not a build decision.
Reason: owner independently spot-checked the raw CSVs and `_manifest.json`
and confirmed they match BUILD-SPEC section 5.4's provenance requirements.
`pytest tests/` passes (4/4) and re-running `python -m src.run_all` a second
time correctly skips every source via cache with no API calls.
Owner consulted: yes — verification performed directly by the owner.

Observed in the raw data, carried into Phase 2 rather than acted on now:
row counts differ across nominally "daily" sources (2,168 rows for
NYSE-hours equity tickers vs. 2,171-2,172 for `GC=F`/`DX-Y.NYB`/`^VIX`
vs. 2,247-2,251 for the daily FRED series vs. 3,151 for Bitcoin), because
each trades on a different calendar. This is exactly the problem BUILD-SPEC
section 6.1 assigns to the Nasdaq-trading-day inner join — nothing to fix
in Phase 1, just a concrete number to point to when explaining why the
calendar alignment step exists.

**2026-09-18 — Wide daily panel format for `panel_daily.parquet`**
Alternatives considered: long format matching section 8's SQL schema
(`prices_daily(date, ticker, close, volume)` etc.) directly.
Reason: Phase 4's rolling-correlation code wants columns to compute
against directly (`close_BTC-USD`, `log_return_^IXIC`, ...); a wide panel
is the natural shape for that, and Phase 3's `database.py` can melt it
into the long SQL tables when it's built. Not fixed by section 7, which
names the file but not its shape.
Owner consulted: no.

**2026-09-18 — `panel_daily_alt_weekend.parquet` as the robustness-check filename**
Alternatives considered: n/a — section 7 doesn't name this file at all,
only requires the alternative panel to exist (section 6.1).
Reason: needed a name; chose one that says what differs (weekend handling)
rather than a generic `_v2` or `_alt` suffix.
Owner consulted: no.

**2026-09-18 — Sentiment gap at 2018-04-16 left as NaN, not forward-filled**
Alternatives considered: forward-filling like M2SL/WALCL, with a matching
is_forward_filled flag.
Reason: sentiment isn't in section 5.2's forward-fill list; extending that
list by assumption for a single missing day wasn't worth it. No value was
published for that day, so none is invented.
Owner consulted: yes, asked directly — owner chose leave-as-NaN.

**2026-09-18 — BTC-USD same-day publication-lag gap: refetched, and the
integrity assertion redesigned around real data instead of a guess**
What happened: the first Phase 2 build run raised the "zero NaN in
close_BTC-USD" assertion — 2026-09-17 was missing from that morning's
cached pull. A fresh yfinance query a few hours later returned it cleanly,
confirming this was Yahoo's BTC-USD feed not having finalized the previous
day's bar yet at pull time, not a permanent gap. The stale cache entry and
CSV were removed and `fetch_market.py` re-run for that one ticker, which
pulled the complete data.
Alternatives considered: leaving the NaN in place and accepting a 2-day
gap in Bitcoin's log return; loosening the assertion instead of refetching.
Reason to refetch rather than loosen: the assertion doing exactly its job
(catching a genuine incomplete pull) is the point of writing it; getting
the real complete data is strictly better than tolerating a hole in it.
Reason to also loosen the assertion going forward: this exposed that the
original zero-tolerance design was based on checking only 6 of 8 tickers
before writing it (see the 2026-09-18 Phase 2 plan) — Bitcoin, trading
right up to the pull time, is uniquely exposed to this lag in a way the
exchange-hours tickers aren't. The assertion now tolerates a NaN only
within the trailing 30 days, matching the tolerance already used for daily
FRED series, and fails loudly on anything older.
Owner consulted: no — investigated and fixed within the session; reported
here rather than left silent.

**2026-09-18 — Daily FRED-series NaN tolerance changed from a trailing-date
window to a NaN-fraction threshold**
What happened: `DFII10`, `DTWEXBGS`, and `T10Y2Y` all have NaNs scattered
across the full study period, not just at the trailing edge — every one
of them lands exactly on Columbus Day or Veterans Day (observed) in every
year from 2018 to 2025, plus a few additional bond-market-only closures
in `DTWEXBGS`. These are Treasury/bond-market holidays that aren't Nasdaq
holidays, so FRED has no reading while Nasdaq was open.
Alternatives considered: hand-maintaining a bond-market holiday calendar
to assert against exactly; keeping the trailing-window-only assertion and
accepting it would always fail for these three series.
Reason: modeling every regional/market holiday calendar precisely is more
machinery than this project needs (see CLAUDE.md's "no abstractions beyond
what's needed"). `FRED_DAILY_MAX_NAN_FRACTION = 0.05` in `src/config.py`
catches a genuinely broken pull (which would leave far more than 5% NaN)
without failing on legitimate, recurring holiday gaps (actual rate: 0.7%
to 1.3% of rows per series). Documented in docs/methodology.md.
Owner consulted: no — investigated and fixed within the session; reported
here rather than left silent.

**2026-09-18 — Phase 2 (panel construction) signed off as complete**
Alternatives considered: n/a — this is a phase closeout, not a build decision.
Reason: owner independently verified the built panel's row counts, date
range, and NaN pattern against the printed summary, and walked through
`src/build_panel.py` line by line (calendar-alignment reindex, the
reindex-then-diff vs. diff-then-reindex robustness check, and the
forward-fill flag) to confirm understanding before signing off. All 9
tests pass (`pytest tests/`); `python -m src.run_all` runs both phases
clean end to end.
Owner consulted: yes — verification and walkthrough performed directly
with the owner.

**2026-09-18 — `rolling_correlations`, `regimes`, and `regime_periods`
created with their final structure in Phase 3, populated later**
Alternatives considered: deferring the CREATE TABLE statements for these
three tables until Phase 4 (correlations) and Phase 5 (regimes) actually
have data to put in them.
Reason: BUILD-SPEC section 8 specifies the full schema as one deliverable
of Phase 3; splitting table creation across phases would mean the schema
in `sql/schema.sql` is incomplete until Phase 5 finishes, contradicting
the "make it real, not decorative" framing of section 8. Creating the
tables now with the right columns and constraints, and leaving them at
zero rows, is honest -- an empty result is not fabricated data. Analysis
queries 1, 2, 4, and 5 in `sql/analysis_queries.sql` return 0 rows against
this database until Phase 4 and Phase 5 run.
Owner consulted: yes -- explicitly requested this framing for Phase 3.

**2026-09-18 — Analysis query 7 reconciles the ETL load against an
independently recomputed check table, not correlation values**
What happened: BUILD-SPEC section 8's literal wording for query 7 is "a
join proving that the correlation values stored in SQLite match those
computed in Pandas." `rolling_correlations` is empty until Phase 4 (see
above), so that query would pass vacuously on 0 rows right now -- not a
real reconciliation, just a query that can't find a disagreement because
there's nothing in it to disagree with.
Alternatives considered: (1) write the literal correlation-value query
now and accept the vacuous pass, re-verifying it for real once Phase 4
populates `rolling_correlations`; (2) reconcile `returns_daily` (built by
melting `panel_daily.parquet` in `src/database.py`) against a second
table, `returns_daily_recomputed_check`, holding the same log returns
recomputed independently with a plain row-by-row loop instead of the
vectorized melt.
Reason chosen (2): it validates real, present data -- the Phase 3 ETL
load -- rather than a table that doesn't exist yet, and it follows the
same "two independently written implementations must agree" principle
BUILD-SPEC section 6.3 already requires for the Phase 4 correlation
functions. The query does execute and pass on real data: 17,344 rows
compared, 0 mismatches. The literal correlation-value reconciliation
section 8 describes gets added once Phase 4 populates
`rolling_correlations`; note this as a Phase 4 follow-up, not forgotten
scope.
Owner consulted: yes -- asked directly, chose option (2).

**2026-09-18 — `pytest.ini` added with `pythonpath = .`**
What happened: CLAUDE.md documents `pytest tests/` as the test command,
but running it bare failed with `ModuleNotFoundError: No module named
'src'` on every test file, including the pre-existing ones from Phase 1
and 2 -- `tests/` has no `__init__.py`, so pytest was adding `tests/`
itself to `sys.path` rather than the repo root. `python -m pytest
tests/` worked around it by relying on `python -m`'s own path insertion,
which is presumably how it passed before, but the documented command did
not actually work standalone.
Alternatives considered: adding `tests/__init__.py`; leaving it
undocumented and always invoking via `python -m pytest`.
Reason: a one-line `pytest.ini` fixes the documented command directly
without turning `tests/` into a package, which is the smaller change.
Owner consulted: no -- pre-existing environment gap found and fixed
while building Phase 3, reported here rather than left silent.

**Observed while building Phase 3, carried forward rather than acted on
now:** query 3's sentiment-bucket grouping includes one row with a blank
`sentiment_bucket` and `n_days = 1` -- this is the documented 2018-04-16
Fear & Greed gap (see the Phase 2 entry above) surfacing again downstream,
not a new data problem.

**Concepts the owner is currently learning, noted here rather than in code comments:**
- The manifest's `has_fetched_today` check is a simple date-string
  comparison, not a general-purpose cache invalidation system — worth being
  able to explain the difference in an interview if asked "how does the
  caching work."
- `reindex-then-diff` vs. `diff-then-reindex` in `build_panel.py` is the
  entire mechanism behind the section 6.1 robustness check: same two pandas
  operations, different order, different answer. Worth being able to trace
  through by hand on a small example (the tests in
  `tests/test_build_panel.py` are exactly that example) rather than just
  citing "calendar alignment" as a phrase.
- Long vs. wide table shape: `panel_daily.parquet` is wide (one column per
  ticker); `prices_daily`/`returns_daily` in SQLite are long (one column
  for `ticker`, one row per ticker per day). `database.py`'s melt
  functions are the conversion. Worth being able to explain why SQL wants
  long (GROUP BY a value in a column) and pandas rolling-window code wants
  wide (a column to call `.rolling()` on directly).
- Window functions in `sql/analysis_queries.sql` (`LAG(...) OVER (ORDER BY
  date ...)` in queries 2 and 5, `SUM(...) OVER (ROWS BETWEEN 1 FOLLOWING
  AND 20 FOLLOWING)` in query 3) compute a value per row using neighboring
  rows, without collapsing rows the way `GROUP BY` does. Worth tracing
  query 3's frame by hand on a few rows to see why `ROWS BETWEEN 1
  FOLLOWING AND 20 FOLLOWING` gives a genuinely forward-looking window and
  why `forward_days_available = 20` is needed to drop the last 20 days of
  the series, which don't have a full 20-day-ahead window to sum.
