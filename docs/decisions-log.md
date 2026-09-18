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

**2026-09-18 — GLD, not GC=F, is the headline `BTC_GOLD` pair**
Alternatives considered: `GC=F` gold futures (BUILD-SPEC section 5.1 calls
it the "hard-asset benchmark" and frames `GLD` only as a robustness check
against it).
Reason: `GLD` trades on the same Nasdaq-anchored calendar the rest of the
panel already uses (section 6.1), so no second calendar-alignment issue is
introduced on top of Bitcoin's. `GC=F` remains available as the section
5.1 robustness check, to be computed separately in Phase 6 validation
under a different pair label, not stored as `BTC_GOLD`.
Owner consulted: yes — section 13 explicitly names "which gold series is
the headline" as a decision requiring the owner's input; asked directly,
owner chose GLD.

**2026-09-18 — Spearman computed by ranking within each window and reusing
the hand-written Pearson function, no `scipy` dependency added**
Alternatives considered: `scipy.stats.spearmanr` (the standard library
call for this); ranking the whole series once, then running pandas'
`.rolling().corr()` on the global ranks.
Reason against the global-rank shortcut: it is not mathematically the same
calculation. Spearman correlation over a window is the Pearson correlation
of that window's own local ranks (1..window_size); global ranks sliced to
a window preserve the same relative order but not the same spacing between
values, and Pearson correlation is not invariant to that kind of
transform. Verified this distinction with a test (`y = x**3`, a monotonic
but non-linear pair): Spearman correctly returns 1.0, Pearson does not.
Reason for the chosen approach over `scipy`: BUILD-SPEC section 11 treats
the package list as a ceiling ("nothing else without asking"); ranking a
90-day window with `pandas.Series.rank()` and calling the already-written
`core_math.pearson_correlation()` on the ranks needed no new dependency
and let the hand-written Pearson function do double duty, which is also
easier to explain in an interview than a second library call.
Owner consulted: no — implementation detail, and the no-new-dependency
default follows directly from section 11.

**2026-09-18 — `CORRELATION_TOLERANCE` kept separate from
`RECONCILIATION_TOLERANCE`**
Alternatives considered: reusing `config.RECONCILIATION_TOLERANCE` (the
Phase 3 constant for the returns reconciliation check) for the Phase 4
pandas-vs-hand-written correlation assertion too.
Reason: both are currently `1e-9` and could theoretically diverge later --
a correlation coefficient runs through more floating-point operations
(two means, two sums of squared deviations, a division) than a single
log-return recomputation, so the two checks are logically different
tolerances that happen to share a value today. Keeping them as separate
`config.py` constants keeps that difference a one-line edit if either
needs loosening.
Owner consulted: no.

**2026-09-18 — `database.main()` no longer runs the analysis-query export;
moved to a new `run_all.run_analysis_queries()` step at the end of the
pipeline**
Alternatives considered: leaving `run_analysis_queries_and_export()` inside
`database.main()`, called from Phase 3, as it was in Phase 3's own build.
Reason: with that arrangement, queries 1, 2, 4, 5, 6, and 8 -- everything
depending on `rolling_correlations` or `regimes`/`regime_periods` -- would
keep exporting 0 rows even after Phase 4 populates `rolling_correlations`,
since Phase 3 runs before Phase 4 in `run_all.main()`. Query export now
runs once, at the very end of the pipeline, after every table any query
depends on has been loaded. `database.py` still owns
`run_analysis_queries_and_export()` and `RECONCILIATION_QUERY_NUMBERS`;
only the call site moved.
Owner consulted: no -- implementation detail needed to make Phase 4's own
acceptance criterion (query results actually populated) true.

**2026-09-18 — Query 8 added: the literal correlation-value reconciliation
BUILD-SPEC section 8 describes, deferred from Phase 3**
What happened: the Phase 3 decisions-log entry for query 7 already flagged
that section 8's literal wording for that slot -- "a join proving that the
correlation values stored in SQLite match those computed in Pandas" -- had
to wait for Phase 4 to populate `rolling_correlations`. `src/correlations.py`
now also writes the 90-day Pearson hand-written values to a second table,
`rolling_correlations_recomputed_check` (schema mirrors
`rolling_correlations`), and query 8 joins the two and asserts zero rows
differ by more than `1e-9` -- the same check `assert_pandas_and_hand_written_agree()`
already does in memory before either table is loaded, re-proved at the SQL
level. `config.ANALYSIS_QUERY_EXPORT_FILENAMES` and
`database.RECONCILIATION_QUERY_NUMBERS` both extended to cover it.
Alternatives considered: leaving query 7 as the only reconciliation query
and treating the in-memory assertion in `src/correlations.py` as
sufficient on its own.
Reason: section 8 says "at least these" queries, so an eighth is within
scope, and a SQL-level proof is what a reviewer reading `sql/analysis_queries.sql`
actually sees, versus having to trust a Python assertion they can't see run.
Owner consulted: no -- this was explicitly flagged as Phase 4 follow-up
work in the Phase 3 entry, not new scope.

**2026-09-18 — Phase 4 (rolling correlations) signed off as complete**
Alternatives considered: n/a -- phase closeout, not a build decision.
Reason: `python -m src.run_all` runs Phase 4 end to end against real data
-- 2,078 non-NaN values per pair at the 90-day window, the pandas/hand-
written agreement assertion passes for all three pairs, and queries 1, 2,
5, and 8 return non-vacuous results (18, 20, 39, and 0 rows respectively).
`pytest tests/` passes (27/27, including the new
`tests/test_core_math.py` and `tests/test_correlations.py`). Figures 1, 2,
and 4 render to `outputs/figures/`, checked visually for greyscale
legibility (each of the three pair lines uses both a distinct color and a
distinct linestyle; every heatmap cell prints its numeric value).
Owner consulted: no -- verification performed by inspecting the pipeline
run's log output and the rendered figures directly.

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
- Pearson vs. Spearman correlation (`src/core_math.py`,
  `src/correlations.py`): Pearson measures linear relationship between the
  raw values; Spearman measures monotonic relationship by first converting
  each value to its rank within the window, then running the exact same
  Pearson formula on the ranks. `tests/test_correlations.py`'s `y = x**3`
  case is the clearest way to see the two methods actually disagree: worth
  being able to explain why Spearman is 1.0 there but Pearson isn't.
- Why a rolling calculation can't rank "the whole series and then slice a
  window" as a shortcut for ranking each window separately
  (`rolling_spearman()`'s docstring works through this): a value's rank
  depends on what else is in the window it's being compared against, so
  the ranking step has to be redone for every window, not done once up
  front.
