# Decisions log

Format: date, decision, alternatives considered, reason, whether the owner
was consulted. Per BUILD-SPEC-bitcoin-regime-study.md section 13, this file
also carries one-line pointers to concepts the owner is currently learning,
rather than turning code comments into a tutorial.

---

**2026-09-18: `src/run_all.py` as the single pipeline entry point, no Makefile**
Alternatives considered: a `Makefile` (BUILD-SPEC section 7's default), a
`run.sh` shell script.
Reason: development is on Windows without `make` installed. A Python entry
point run as `python -m src.run_all` needs no extra tooling and works the
same in PowerShell as anywhere else.
Owner consulted: yes, explicitly requested.

**2026-09-18: Raw cache files saved as CSV, not Parquet**
Alternatives considered: Parquet (BUILD-SPEC section 5.4 allows either).
Reason: CSV is readable by eye in a text editor, which matters for a
beginner debugging a failed or malformed pull. Parquet is used from Phase 2
onward for the processed panel, where file size and dtype fidelity start to
matter more than eyeballing.
Owner consulted: no, implementation detail already left open by the spec,
decided per section 13's "do not ask about implementation detail already
specified here."

**2026-09-18: `src/manifest.py` added as a shared helper module**
Alternatives considered: duplicating manifest read/write/cache-check logic
inside each of `fetch_market.py`, `fetch_fred.py`, and `fetch_sentiment.py`.
Reason: all three fetch modules need to record the same provenance fields
(BUILD-SPEC section 5.4) and apply the same same-day caching rule; one
shared module means that logic is tested and fixed in one place. Not listed
in BUILD-SPEC section 7's repo tree, but adding small internal helper
modules is an implementation detail, not a scope change.
Owner consulted: no.

**2026-09-18: `pyarrow` added to requirements.txt in Phase 1**
Alternatives considered: adding it only when Phase 2 first writes
`panel_daily.parquet`.
Reason: it's a direct dependency for the Parquet output the repo structure
(BUILD-SPEC section 7) already commits to, and pinning it alongside the
rest of the stack now avoids a mid-project requirements.txt churn. Not
named explicitly in section 11's package list, which is otherwise treated
as the ceiling on dependencies ("nothing else without asking"), flagged
here rather than silently added.
Owner consulted: no.

**2026-09-18: Phase 1 (data acquisition) signed off as complete**
Alternatives considered: n/a, this is a phase closeout, not a build decision.
Reason: owner independently spot-checked the raw CSVs and `_manifest.json`
and confirmed they match BUILD-SPEC section 5.4's provenance requirements.
`pytest tests/` passes (4/4) and re-running `python -m src.run_all` a second
time correctly skips every source via cache with no API calls.
Owner consulted: yes, verification performed directly by the owner.

Observed in the raw data, carried into Phase 2 rather than acted on now:
row counts differ across nominally "daily" sources (2,168 rows for
NYSE-hours equity tickers vs. 2,171-2,172 for `GC=F`/`DX-Y.NYB`/`^VIX`
vs. 2,247-2,251 for the daily FRED series vs. 3,151 for Bitcoin), because
each trades on a different calendar. This is exactly the problem BUILD-SPEC
section 6.1 assigns to the Nasdaq-trading-day inner join, nothing to fix
in Phase 1, just a concrete number to point to when explaining why the
calendar alignment step exists.

**2026-09-18: Wide daily panel format for `panel_daily.parquet`**
Alternatives considered: long format matching section 8's SQL schema
(`prices_daily(date, ticker, close, volume)` etc.) directly.
Reason: Phase 4's rolling-correlation code wants columns to compute
against directly (`close_BTC-USD`, `log_return_^IXIC`, ...); a wide panel
is the natural shape for that, and Phase 3's `database.py` can melt it
into the long SQL tables when it's built. Not fixed by section 7, which
names the file but not its shape.
Owner consulted: no.

**2026-09-18: `panel_daily_alt_weekend.parquet` as the robustness-check filename**
Alternatives considered: n/a, section 7 doesn't name this file at all,
only requires the alternative panel to exist (section 6.1).
Reason: needed a name; chose one that says what differs (weekend handling)
rather than a generic `_v2` or `_alt` suffix.
Owner consulted: no.

**2026-09-18: Sentiment gap at 2018-04-16 left as NaN, not forward-filled**
Alternatives considered: forward-filling like M2SL/WALCL, with a matching
is_forward_filled flag.
Reason: sentiment isn't in section 5.2's forward-fill list; extending that
list by assumption for a single missing day wasn't worth it. No value was
published for that day, so none is invented.
Owner consulted: yes, asked directly, owner chose leave-as-NaN.

**2026-09-18: BTC-USD same-day publication-lag gap: refetched, and the
integrity assertion redesigned around real data instead of a guess**
What happened: the first Phase 2 build run raised the "zero NaN in
close_BTC-USD" assertion, 2026-09-17 was missing from that morning's
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
before writing it (see the 2026-09-18 Phase 2 plan), Bitcoin, trading
right up to the pull time, is uniquely exposed to this lag in a way the
exchange-hours tickers aren't. The assertion now tolerates a NaN only
within the trailing 30 days, matching the tolerance already used for daily
FRED series, and fails loudly on anything older.
Owner consulted: no, investigated and fixed within the session; reported
here rather than left silent.

**2026-09-18: Daily FRED-series NaN tolerance changed from a trailing-date
window to a NaN-fraction threshold**
What happened: `DFII10`, `DTWEXBGS`, and `T10Y2Y` all have NaNs scattered
across the full study period and not only at the trailing edge, every one
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
Owner consulted: no, investigated and fixed within the session; reported
here rather than left silent.

**2026-09-18: Phase 2 (panel construction) signed off as complete**
Alternatives considered: n/a, this is a phase closeout, not a build decision.
Reason: owner independently verified the built panel's row counts, date
range, and NaN pattern against the printed summary, and walked through
`src/build_panel.py` line by line (calendar-alignment reindex, the
reindex-then-diff vs. diff-then-reindex robustness check, and the
forward-fill flag) to confirm understanding before signing off. All 9
tests pass (`pytest tests/`); `python -m src.run_all` runs both phases
clean end to end.
Owner consulted: yes, verification and walkthrough performed directly
with the owner.

**2026-09-18: `rolling_correlations`, `regimes`, and `regime_periods`
created with their final structure in Phase 3, populated later**
Alternatives considered: deferring the CREATE TABLE statements for these
three tables until Phase 4 (correlations) and Phase 5 (regimes) actually
have data to put in them.
Reason: BUILD-SPEC section 8 specifies the full schema as one deliverable
of Phase 3; splitting table creation across phases would mean the schema
in `sql/schema.sql` is incomplete until Phase 5 finishes, contradicting
the "make it real, not decorative" framing of section 8. Creating the
tables now with the right columns and constraints, and leaving them at
zero rows, is honest, an empty result is not fabricated data. Analysis
queries 1, 2, 4, and 5 in `sql/analysis_queries.sql` return 0 rows against
this database until Phase 4 and Phase 5 run.
Owner consulted: yes, explicitly requested this framing for Phase 3.

**2026-09-18: Analysis query 7 reconciles the ETL load against an
independently recomputed check table, not correlation values**
What happened: BUILD-SPEC section 8's literal wording for query 7 is "a
join proving that the correlation values stored in SQLite match those
computed in Pandas." `rolling_correlations` is empty until Phase 4 (see
above), so that query would pass vacuously on 0 rows right now, not a
real reconciliation, just a query that can't find a disagreement because
there's nothing in it to disagree with.
Alternatives considered: (1) write the literal correlation-value query
now and accept the vacuous pass, re-verifying it for real once Phase 4
populates `rolling_correlations`; (2) reconcile `returns_daily` (built by
melting `panel_daily.parquet` in `src/database.py`) against a second
table, `returns_daily_recomputed_check`, holding the same log returns
recomputed independently with a plain row-by-row loop instead of the
vectorized melt.
Reason chosen (2): it validates real, present data, the Phase 3 ETL
load, rather than a table that doesn't exist yet, and it follows the
same "two independently written implementations must agree" principle
BUILD-SPEC section 6.3 already requires for the Phase 4 correlation
functions. The query does execute and pass on real data: 17,344 rows
compared, 0 mismatches. The literal correlation-value reconciliation
section 8 describes gets added once Phase 4 populates
`rolling_correlations`; note this as a Phase 4 follow-up, not forgotten
scope.
Owner consulted: yes, asked directly, chose option (2).

**2026-09-18: `pytest.ini` added with `pythonpath = .`**
What happened: CLAUDE.md documents `pytest tests/` as the test command,
but running it bare failed with `ModuleNotFoundError: No module named
'src'` on every test file, including the pre-existing ones from Phase 1
and 2, `tests/` has no `__init__.py`, so pytest was adding `tests/`
itself to `sys.path` rather than the repo root. `python -m pytest
tests/` worked around it by relying on `python -m`'s own path insertion,
which is presumably how it passed before, but the documented command did
not actually work standalone.
Alternatives considered: adding `tests/__init__.py`; leaving it
undocumented and always invoking via `python -m pytest`.
Reason: a one-line `pytest.ini` fixes the documented command directly
without turning `tests/` into a package, which is the smaller change.
Owner consulted: no, pre-existing environment gap found and fixed
while building Phase 3, reported here rather than left silent.

**Observed while building Phase 3, carried forward rather than acted on
now:** query 3's sentiment-bucket grouping includes one row with a blank
`sentiment_bucket` and `n_days = 1`, this is the documented 2018-04-16
Fear & Greed gap (see the Phase 2 entry above) surfacing again downstream,
not a new data problem.

**2026-09-18: GLD, not GC=F, is the headline `BTC_GOLD` pair**
Alternatives considered: `GC=F` gold futures (BUILD-SPEC section 5.1 calls
it the "hard-asset benchmark" and frames `GLD` only as a robustness check
against it).
Reason: `GLD` trades on the same Nasdaq-anchored calendar the rest of the
panel already uses (section 6.1), so no second calendar-alignment issue is
introduced on top of Bitcoin's. `GC=F` remains available as the section
5.1 robustness check, to be computed separately in Phase 6 validation
under a different pair label, not stored as `BTC_GOLD`.
Owner consulted: yes, section 13 explicitly names "which gold series is
the headline" as a decision requiring the owner's input; asked directly,
owner chose GLD.

**2026-09-18: Spearman computed by ranking within each window and reusing
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
Owner consulted: no, implementation detail, and the no-new-dependency
default follows directly from section 11.

**2026-09-18: `CORRELATION_TOLERANCE` kept separate from
`RECONCILIATION_TOLERANCE`**
Alternatives considered: reusing `config.RECONCILIATION_TOLERANCE` (the
Phase 3 constant for the returns reconciliation check) for the Phase 4
pandas-vs-hand-written correlation assertion too.
Reason: both are currently `1e-9` and could theoretically diverge later, a correlation coefficient runs through more floating-point operations
(two means, two sums of squared deviations, a division) than a single
log-return recomputation, so the two checks are logically different
tolerances that happen to share a value today. Keeping them as separate
`config.py` constants keeps that difference a one-line edit if either
needs loosening.
Owner consulted: no.

**2026-09-18: `database.main()` no longer runs the analysis-query export;
moved to a new `run_all.run_analysis_queries()` step at the end of the
pipeline**
Alternatives considered: leaving `run_analysis_queries_and_export()` inside
`database.main()`, called from Phase 3, as it was in Phase 3's own build.
Reason: with that arrangement, queries 1, 2, 4, 5, 6, and 8, everything
depending on `rolling_correlations` or `regimes`/`regime_periods`, would
keep exporting 0 rows even after Phase 4 populates `rolling_correlations`,
since Phase 3 runs before Phase 4 in `run_all.main()`. Query export now
runs once, at the very end of the pipeline, after every table any query
depends on has been loaded. `database.py` still owns
`run_analysis_queries_and_export()` and `RECONCILIATION_QUERY_NUMBERS`;
only the call site moved.
Owner consulted: no, implementation detail needed to make Phase 4's own
acceptance criterion (query results actually populated) true.

**2026-09-18: Query 8 added: the literal correlation-value reconciliation
BUILD-SPEC section 8 describes, deferred from Phase 3**
What happened: the Phase 3 decisions-log entry for query 7 already flagged
that section 8's literal wording for that slot, "a join proving that the
correlation values stored in SQLite match those computed in Pandas", had
to wait for Phase 4 to populate `rolling_correlations`. `src/correlations.py`
now also writes the 90-day Pearson hand-written values to a second table,
`rolling_correlations_recomputed_check` (schema mirrors
`rolling_correlations`), and query 8 joins the two and asserts zero rows
differ by more than `1e-9`, the same check `assert_pandas_and_hand_written_agree()`
already does in memory before either table is loaded, re-proved at the SQL
level. `config.ANALYSIS_QUERY_EXPORT_FILENAMES` and
`database.RECONCILIATION_QUERY_NUMBERS` both extended to cover it.
Alternatives considered: leaving query 7 as the only reconciliation query
and treating the in-memory assertion in `src/correlations.py` as
sufficient on its own.
Reason: section 8 says "at least these" queries, so an eighth is within
scope, and a SQL-level proof is what a reviewer reading `sql/analysis_queries.sql`
actually sees, versus having to trust a Python assertion they can't see run.
Owner consulted: no, this was explicitly flagged as Phase 4 follow-up
work in the Phase 3 entry, not new scope.

**2026-09-18: Phase 4 (rolling correlations) signed off as complete**
Alternatives considered: n/a, phase closeout, not a build decision.
Reason: `python -m src.run_all` runs Phase 4 end to end against real data, 2,078 non-NaN values per pair at the 90-day window, the pandas/hand-
written agreement assertion passes for all three pairs, and queries 1, 2,
5, and 8 return non-vacuous results (18, 20, 39, and 0 rows respectively).
`pytest tests/` passes (27/27, including the new
`tests/test_core_math.py` and `tests/test_correlations.py`). Figures 1, 2,
and 4 render to `outputs/figures/`, checked visually for greyscale
legibility (each of the three pair lines uses both a distinct color and a
distinct linestyle; every heatmap cell prints its numeric value).
Owner consulted: no, verification performed by inspecting the pipeline
run's log output and the rendered figures directly.

**2026-09-18: Persistence filter merges a short run into the preceding
regime, not the following one**
What happened: BUILD-SPEC section 6.4 says a run shorter than 15 trading
days is "relabelled to the surrounding regime" but doesn't say which side
when the run sits between two *different* regimes.
Alternatives considered: merge into the following run instead; merge into
whichever neighbor is longer; split the short run and assign each half to
its nearer neighbor.
Reason: merging backward (into the preceding run) reads as "a brief blip
during an established regime doesn't rewrite the regime that came before
it", the standard forward-fill-from-last-stable-state interpretation.
The only exception is a short run at the very start of the series, which
has no preceding run and instead borrows the label of the run that
follows it. `src/regimes.py:apply_persistence_filter()` implements this
by repeatedly merging short runs (a merge can make a run long enough to
then swallow its own next short neighbor) until every surviving run
clears the minimum.
Owner consulted: yes, flagged explicitly in the Phase 5 plan per
section 13 ("ask before assuming on anything that changes the meaning of
a result"), since this determines the exact regime boundary dates in the
timeline table. Confirmed before building.

**2026-09-18: Regime timeline via a new SQL query 9; per-regime summary
statistics and the sensitivity grid computed directly in `src/regimes.py`,
not through `sql/analysis_queries.sql`**
Alternatives considered: writing every Phase 5 output as a SQL query, to
keep query export as the single path for everything in outputs/tables/.
Reason: the regime timeline (`regime_periods` ordered by start date) is a
direct SQL SELECT, so it became query 9, alongside query 4's aggregated
per-label view, the same "make SQL do real work" reasoning already
applied to queries 1-8. Per-regime statistics (annualized return,
annualized volatility, maximum drawdown, average Fear & Greed level) mix
price, return, and sentiment data with the hand-written stat functions in
`src/core_math.py`, a pandas computation, not a SQL join, so it's
written directly to `outputs/tables/regime_summary_statistics.csv`. The
sensitivity grid re-runs the whole classify-then-filter pipeline 25 times
with different thresholds, which isn't expressible as a SQL query against
data already in the database at all, it recomputes classification, it
doesn't query stored results, so it's also Python-computed, to
`outputs/tables/sensitivity_grid.csv`.
Owner consulted: no, implementation detail, decided and logged per
section 13.

**2026-09-18: Chart generation moved out of Phase 4 and into its own
step, run after Phase 5**
What happened: `charts.main()` was called from inside
`run_phase_4_correlations()`, generating figures 1, 2, and 4. Figure 1
now needs `regime_periods` for its shaded bands, and figures 3 and 5 need
`regime_periods` and `outputs/tables/sensitivity_grid.csv` directly,
neither of which exists until Phase 5 runs.
Alternatives considered: regenerating figure 1 a second time after Phase
5 while leaving the Phase-4 call in place.
Reason: a single `run_charts()` step, called once after Phase 5 (mirroring
`run_analysis_queries()`'s move out of Phase 3 in the Phase 3 entry
above), is simpler than generating figure 1 twice. `charts.main()` now
generates all five figures in one pass.
Owner consulted: no, implementation detail needed to make the Phase 5
acceptance criterion (figures 3 and 5 render) true without breaking figure
1. Decided and logged per section 13.

**2026-09-18: Annualized return on short regime periods flagged as a
caveat, not suppressed or reformulated**
What happened: the 20-trading-day `MIXED` period (2020-12-14 to
2021-01-12, the start of Bitcoin's late-2020 rally) annualizes to a
return figure of 2,816.80 (281,680%), correct given the formula
(scaling a short window's average daily log return up to a full year),
but not a usable estimate of anything.
Alternatives considered: suppressing annualized return for periods under
some length threshold; reporting cumulative period return instead of
annualized return for short periods; adding a second config threshold to
switch formulas.
Reason not to change the metric: BUILD-SPEC section 6.4 asks for
annualized return as a per-regime statistic without a length exception,
and the number is not fabricated, it is exactly what the stated formula
produces. Silently changing the definition for some rows and not others
would make the table harder to trust, not easier. Per section 13 ("when a
result looks too good, say so and investigate before reporting it"), the
right response is a caveat in `docs/methodology.md`, not a quiet
reformulation.
Owner consulted: no, an honesty flag on a real computed result, not a
decision with more than one reasonable outcome. Documented rather than
silently reported.

**2026-09-18: Phase 5 (regime classification) signed off as complete**
Alternatives considered: n/a, phase closeout, not a build decision.
Reason: `python -m src.run_all` runs Phase 5 end to end against real
data, 2,078 classified days, 16 regime periods after the persistence
filter (matching the count independently verified against the live
`rolling_correlations` table before any code was written), the 25-
combination sensitivity grid runs and the 2026 regime shift survives all
25, and figures 1 (now with regime bands), 3, and 5 render. `pytest
tests/` passes (43/43, including the new `tests/test_regimes.py` and the
new `core_math` stat-function tests in `tests/test_core_math.py`).
Queries 4, 6, and 9 return non-vacuous results (4, 4, and 16 rows).
Owner consulted: yes, thresholds, the persistence filter, and the
sensitivity grid were confirmed against BUILD-SPEC section 6.4/6.5 and
against a before/after label-stability comparison before any Phase 5 code
was written.

**2026-09-18: `rolling_correlations_validation` as its own table, not appended to `rolling_correlations`**
Alternatives considered: giving `BTC_NASDAQ_NDX` and `BTC_GOLD_GCF` new
pair labels and loading them into the existing `rolling_correlations`
table alongside the headline pairs.
Reason: `database.py:load_dataframe_to_table()` asserts the table's
*total* row count equals the number of rows just inserted, an assertion
that only holds when the table was empty before the call. By the time
Phase 6 runs, `rolling_correlations` already holds Phase 4's rows, so
appending into it would trip a false assertion failure (or require
weakening a working, tested check). A dedicated table follows the
precedent `rolling_correlations_recomputed_check` already set, and keeps
Phase 6's alternate-instrument series out of every analysis query that
filters `rolling_correlations` by pair, none of which expect them.
Owner consulted: no, a correctness constraint found while reading
`database.py`, not a judgment call.

**2026-09-18: No SQL-level hand-written-check table for the Phase 6 validation pairs**
Alternatives considered: mirroring Phase 4 exactly, with a second new
table (`rolling_correlations_validation_recomputed_check`) and a tenth
analysis query reconciling it.
Reason: the pandas/hand-written agreement is still computed and asserted
at run time (same two functions, same `CORRELATION_TOLERANCE`, same
`assert_pandas_and_hand_written_agree()` call Phase 4 uses), but
persisting a second reconciliation table would add SQL surface with no
analysis question that needs it, since `BTC_NASDAQ_NDX`/`BTC_GOLD_GCF` are
one-off robustness checks against specific published dates, not new
headline figures BUILD-SPEC section 6.3's dual-implementation mandate is
scoped to.
Owner consulted: no.

**2026-09-18: Bitwise's "as-of" date is 2026-08-31 (data-through), not 2026-09-03 (report-publish)**
Alternatives considered: using the 2026-09-03 publish date; showing both
dates as full, separate comparison rows.
Reason: Bitwise's own report states its Bloomberg data runs through
August 31; comparing our correlation on that exact date is the
methodologically correct reading of "as-of," not the date a news outlet
happened to cover it. The 09-03 reading is shown as a one-line footnote in
`docs/validation.md` instead of a second full row, since it's the same
underlying claim, not a fifth published figure.
Owner consulted: yes, confirmed via AskUserQuestion before writing
`docs/validation.md`.

**2026-09-18: Bitwise's Nasdaq figure uses 0.30 (both fetched outlets), with the 0.33 outlet variance disclosed as a footnote, not a fifth comparison row**
Alternatives considered: treating 0.33 (The Block) as a separate claim
from 0.30 (24-7 Wall St.), each with its own row.
Reason: both numbers describe the same underlying Bitwise report; treating
outlet-to-outlet rounding/paraphrase variance as two different published
claims would double-count one reading as two. Disclosed directly in
`docs/sources.md` instead, per CLAUDE.md's fabrication rule, the goal is
to be honest about what the sources actually say, not to manufacture more
comparison rows.
Owner consulted: no.

**2026-09-18: Phase 6 (validation) complete: `docs/sources.md`, `docs/validation.md`, `src/validation.py`, figure 10**
Alternatives considered: n/a, this is a phase closeout, not a build
decision.
Reason: `python -m src.run_all` runs Phase 6 end to end against real data,
between Phase 5 and figure generation, `BTC_NASDAQ_NDX` and
`BTC_GOLD_GCF` computed at the 90-day Pearson window (2,078 non-NaN values
each, pandas and hand-written agree within `CORRELATION_TOLERANCE`),
loaded into the new `rolling_correlations_validation` table, and the
4-row `outputs/tables/validation_comparison.csv` built from real,
independently sourced published figures (see `docs/sources.md`) compared
against our own computed values. Both Bitwise robustness-check rows land
far closer to the published figure than the headline pair does (gold:
+0.053 delta on GLD vs. -0.007 on GC=F; Nasdaq: +0.050 delta on Composite
vs. +0.016 on Nasdaq-100), which is real evidence the named instrument
difference explains most of the gap, not an assumption. Figure 10 renders
with explicit `ax.set_xlim()` pinned to the correlation series' own date
range, since `ax.annotate()`'s callout boxes otherwise pull matplotlib's
autoscale well past the last real data point. `pytest tests/` passes
(47/47, including the new `tests/test_validation.py`).
Owner consulted: yes, the Bitwise as-of date and figure 10's x-axis
scope were confirmed via AskUserQuestion before implementation.

**2026-09-18: Phase 7: sentiment buckets computed from `fng_value` against the section 6.6 thresholds, not from the vendor's own `fng_label`**
Alternatives considered: reusing `sentiment_daily.fng_label`, the 5-category
classification alternative.me already assigns ("Extreme Fear", "Fear",
"Neutral", "Greed", "Extreme Greed") and that query 3 already groups by.
Reason: checking the actual panel data, alternative.me's own "Extreme Fear"
band runs from value 5 up to 25, and "Extreme Greed" from 76 to 95, not
the <=20 / >=80 convention BUILD-SPEC section 6.6 explicitly specifies.
`src/sentiment.py:assign_sentiment_bucket()` classifies every day into
EXTREME_FEAR (<=20), EXTREME_GREED (>=80), or MODERATE directly from
`fng_value`, using `config.SENTIMENT_EXTREME_FEAR_MAX` /
`SENTIMENT_EXTREME_GREED_MIN`, so the two schemes don't get silently
conflated. `fng_label` is left untouched for anything that still wants the
vendor's own 5-way split (query 3 is unaffected).
Owner consulted: yes, confirmed via AskUserQuestion before implementation.

**2026-09-18: Phase 7: forward-return summary (n/mean/median/std) computed in pandas, not SQL; the sentiment x regime cross-tab computed in SQL**
Alternatives considered: extending query 3's SQL window-function pattern to
all four horizons and adding mean/median/std there too, matching how
`sql/analysis_queries.sql` already does the 20-day case.
Reason: SQLite has no built-in median or percentile function, and section
6.6 requires the median as well as the mean for every reported statistic. The
cross-tab (query 10) only needs counts, so it stays in SQL, consistent with
every other count-only analysis question in this project. Same split
already used in Phase 5 for `compute_regime_summary_statistics()` vs. the
regime_periods/regimes tables.
Owner consulted: no, follows the Phase 5 precedent already logged above.

**2026-09-18: Phase 7: added a quantitative distance-to-transition table beyond the section 6.6 cross-tab**
Alternatives considered: answering "do extremes cluster near transitions"
with prose only, eyeballing figures 3 and 6 side by side.
Reason: `src/sentiment.py:compute_days_to_nearest_transition()` gives a real
number to discuss instead of an impression, for every day, the number of
trading days to the nearest regime-period boundary, then n/mean/median of
that distance per sentiment bucket
(`outputs/tables/sentiment_transition_proximity.csv`). No significance test
run on it, per section 6.6's explicit ban on significance claims here.
Owner consulted: yes, confirmed via AskUserQuestion before implementation.

**2026-09-18: Figure 7's box-plot "n=" labels anchored to each box's own whisker cap, not the raw column max**
Alternatives considered: the first version placed each label at
`forward_log_return.max()` for its horizon (one shared height for all three
boxes).
Reason: `showfliers=False` hides outlier points from the drawn plot, but a
column's raw max can still be a hidden outlier sitting far above the
visible whiskers, the first render placed labels well above the axes,
overlapping the subplot titles and even the figure's suptitle. Fixed by
reading each box's high whisker cap directly from `ax.boxplot()`'s returned
`bplot["caps"]` and expanding `ax.set_ylim()` with a proportional margin
before placing text, so every label sits just above its own box regardless
of that bucket's outliers.
Owner consulted: no, caught and fixed while reviewing the rendered figure.

**2026-09-18: Phase 8's `dxy_change_20` feature reads the market ticker (`DX-Y.NYB`), not the FRED broad-dollar series (`DTWEXBGS`)**
Alternatives considered: `DTWEXBGS`, the FRED nominal broad US Dollar
Index already pulled in Phase 1 and described in `config.py` as the
"dollar-strength driver."
Reason: the `BTC_DXY` correlation pair the model also uses as a feature
(`corr_30_BTC_DXY`, `corr_90_BTC_DXY`) is built from `DX-Y.NYB`'s log
return. Reading the DXY *change* feature from the same instrument keeps
"DXY" meaning one consistent thing across the feature set, rather than the
correlation feature and the change feature quietly describing two
different dollar indices with different construction methodologies.
Owner consulted: no, implementation detail, section 6.7 names "DXY"
without specifying an instrument.

**2026-09-18: Decision tree depth fixed at 4, not searched within the allowed 3-5 range**
Alternatives considered: trying all of 3, 4, and 5 and reporting whichever
scored best on the walk-forward folds.
Reason: section 6.7 explicitly forbids tuning parameters to try to beat
the persistence baseline. Picking a depth *after* seeing which one scores
best on held-out folds is tuning, even if the search space is small and
the metric isn't accuracy specifically, it's still using test-fold
performance to choose a hyperparameter. 4 is the middle of the allowed
range and still small enough for figure 9 to be readable.
Owner consulted: no, direct consequence of section 6.7's own honesty
requirement.

**2026-09-18: `TimeSeriesSplit(gap=config.ML_TARGET_HORIZON_DAYS)`**
Alternatives considered: `TimeSeriesSplit` with the default `gap=0`.
Reason: the target at any row is dated `ML_TARGET_HORIZON_DAYS` trading
days ahead of that row's features. With `gap=0`, the last few rows of
every training fold would carry a target label dated inside the
following test fold's date range, not feature leakage, but the model
would have been trained on a label that names a day inside the period
it's then evaluated on. Setting the gap equal to the horizon removes that
overlap entirely. See `docs/ml-caveats.md` for why this does not make
the remaining rows independent of each other, it only fixes this one
specific overlap.
Owner consulted: yes, explained in the phase-8 planning conversation
before building, at the owner's explicit request to explain why a
shuffled split would be invalid here.

**2026-09-18: Model comparison metrics computed on pooled out-of-fold predictions, not averaged per-fold metrics**
Alternatives considered: computing accuracy/balanced accuracy/macro F1
per fold and averaging the five fold-level numbers.
Reason: `TimeSeriesSplit`'s expanding-window folds have very different
test-set sizes (each fold's test set is roughly the same length, but the
early folds' training sets are much shorter), so a plain average across
folds would silently weight a fold with 40 test days the same as one with
400. Pooling every fold's out-of-fold predictions before scoring weights
every test day equally instead. The per-fold breakdown is not thrown
away, it's still written to `outputs/tables/ml_per_fold_metrics.csv` so
fold-to-fold stability (or the lack of it) stays visible.
Owner consulted: no, implementation detail.

**2026-09-18: Figure 9's decision tree is fit on the full study history, illustratively, and is never scored**
Alternatives considered: plotting one fold's tree from the walk-forward
loop, e.g. the last fold's.
Reason: any single fold's tree was trained on less data than is
available and would misrepresent what the study's own history actually
shows; using the full-history tree for the figure, while being explicit
in the caption and in `src/model.py` that it is never the tree whose
predictions appear in `ml_model_comparison.csv`, keeps the walk-forward
evaluation (the only place accuracy claims are allowed to come from)
completely separate from the illustration.
Owner consulted: no, implementation detail, doesn't affect any reported
metric.

**2026-09-18: Figures 8 and 9 rendered directly from `src/model.py:main()`, not from `charts.py:main()`**
Alternatives considered: writing the confusion-matrix arrays and the
illustrative tree's structure to disk and having `charts.py:main()` read
them back in, the way it reads `sensitivity_grid.csv` or
`validation_comparison.csv` for other figures.
Reason: same reasoning `src/regimes.py` already uses for the before/after
persistence-filter diagnostic chart, the fitted `DecisionTreeClassifier`
object figure 9 needs isn't naturally something to reload from a CSV
without re-fitting it, and re-fitting inside `charts.py` would put
model-fitting logic in the one module that's supposed to only plot.
`build_confusion_matrices()`'s long-format CSV *does* persist and could
technically be pivoted back in `charts.py`, but keeping both Phase 8
figures generated from the same place (`model.py:main()`) was judged more
consistent than splitting them.
Owner consulted: no, implementation detail.

**2026-09-18: Phase 8 (ML classifier) complete: `src/model.py`, figures 8-9, `docs/ml-caveats.md`, `docs/findings.md`**
Alternatives considered: n/a, this is a phase closeout, not a build
decision.
Reason: `python -m src.run_all` runs Phase 8 end to end against real data,
between Phase 7 and figure generation, 2,045 usable rows after warm-up
and end-of-series drops, walk-forward evaluated across 5
`TimeSeriesSplit(gap=5)` folds (1,700 pooled out-of-fold predictions,
2019-10-31 through 2026-09-10). Result matches section 6.7's expected
headline exactly: the persistence baseline (accuracy 0.962, balanced
accuracy 0.944, macro F1 0.949) beats both the decision tree (0.841,
0.733, 0.722) and logistic regression (0.676, 0.563, 0.559), and neither
model's hyperparameters were adjusted after seeing this. `docs/findings.md`
states the comparison as the headline, per section 6.7's honesty
requirement, and walks through the illustrative full-history tree
(figure 9) to explain *why*: its first split is the current-regime
feature, the same information the persistence baseline already uses
directly. `pytest tests/` passes (57/57, including the new
`tests/test_model.py`).
Owner consulted: yes, the full Phase 8 plan (task, features, models,
validation scheme, both baselines, metrics, the honesty requirement) was
confirmed via ExitPlanMode before implementation, per the owner's
explicit request to plan before building.

**2026-09-18: Phase 9: fetch cache left expiring after one UTC day, documented instead of changed**
Alternatives considered: adding a flag so the default run uses the committed
snapshot regardless of date; leaving the cache logic as is and documenting
the consequence.
Reason: `manifest.has_fetched_today` compares the retrieval date with
today's UTC date, so a run on any later day re-fetches, needs a FRED key,
and moves the sample end date. Changing fetch semantics is a code change
outside a documentation phase. The README and `docs/limitations.md` state
the consequence, and the snapshot flag is in `docs/future-work.md`.
Owner consulted: yes, recommended option accepted.

**2026-09-18: Phase 9: `src/robustness.py` added, writing four tables**
Alternatives considered: leaving the section 6.1 (weekend handling) and
section 6.3 (Pearson versus Spearman) results only in figures and SQLite;
quoting them in the docs without a table.
Reason: the spec requires both results to be reported, and section 7 says
`outputs/tables/` holds every number quoted in the write-up. The module
reads the two panels and `rolling_correlations` and adds no new data. It
writes `robustness_weekend_handling.csv`, `robustness_pearson_vs_spearman.csv`,
`robustness_window_30_vs_90.csv` and `correlation_latest_snapshot.csv`. The
0.10 threshold for a "notable" Pearson-Spearman gap is
`config.ROBUSTNESS_NOTABLE_DIFFERENCE`, a reporting threshold that nothing
downstream reads. `run_all` runs it as Phase 9, after Phase 8 and before
figure generation. `tests/test_robustness.py` covers it.
Owner consulted: yes, recommended option accepted.

**2026-09-18: Phase 9: `requirements.txt` pins all 45 installed packages**
Alternatives considered: pinning only the 9 direct dependencies.
Reason: the spec asks for pinned versions and determinism. Pinning the 36
transitive packages as well means a fresh install reproduces the exact
environment. I verified it: a new virtual environment built from the file
has a `pip freeze` identical to it. My Phase 9 plan said 43 packages and 34
transitive. The real counts are 45 and 36.
Owner consulted: yes, recommended option accepted.

**2026-09-18: Phase 9: figure 5 changed, and the em-dash and double-hyphen asides removed from this log**
Alternatives considered: leaving both as they were.
Reason: section 10 bans em-dash tics, and the owner asked for the rules to
be applied strictly, so entry headers now use a colon and other dashes
became commas. In `src/charts.py`, figure 5's pass/fail marks were dingbat
glyphs, now the words "yes" and "no". While re-rendering I found two
existing defects and fixed them. The caption was one very long line that
stretched the image to 2,375 pixels wide, so I broke it in two (now 1,199
wide). The cell labels were all white, because the contrast midpoint was
`max * 0.6` and every cell is at least 13, so I set it to the midpoint of
the value range. No other figure or table changed when I regenerated
everything.
Owner consulted: yes for the glyph change. No for the caption and contrast
fixes, which I found and fixed within the session.

**2026-09-18: Phase 9: `docs/findings.md` rewritten as five findings, and a correction to earlier text**
Alternatives considered: appending phases 1 to 7 headlines to the Phase 8
section.
Reason: section 15 asks for three to five findings, each with a number, a
figure and a caveat. I checked every number by hand against the tables it
cites. A throwaway script confirmed that each number appears in some table.
That script is a weak backstop, because small numbers match easily, so the
hand check is what I rely on. I dropped a claim from the old text, the date
range of the test folds, because no table holds it. I also corrected an
error in `docs/methodology.md` and in an earlier entry of this log. Both
said the 20-day MIXED period annualises to "thousands of percent". The
figure in `regime_summary_statistics.csv` is 2,816.80 as a fraction, which
is 281,680%.
Owner consulted: no, a documentation task within the plan the owner approved.

**2026-09-18: Phase 9: test added for "no NaN reaches the modelling dataset"**
Alternatives considered: relying on the `dropna` in `build_feature_matrix`.
Reason: section 11 lists this test as required, and I found none in
`tests/test_model.py`. I nearly wrote a sentence in `docs/methodology.md`
claiming that a test existed. I added the test instead
(`test_build_feature_matrix_leaves_no_nan_in_the_modelling_dataset`).
Owner consulted: no, a required item found missing.

**2026-09-18: Phase 9 (documentation and packaging) complete**
Alternatives considered: n/a, this is a phase closeout, not a build decision.
Reason: all nine files under `docs/` exist. `README.md` is 563 words by a
whitespace count that includes code and table syntax. A style scan of the
README and every doc except the build spec found no emoji, banned words,
em dashes or double-hyphen asides. I verified the definition of done from
section 15 in a clean copy of the tracked files, with no `.env`, no
`data/processed/` and a new virtual environment built from
`requirements.txt`. `pytest tests/` passed 63 of 63. `python -m src.run_all`
completed using the cache for all 14 series, and all 37 regenerated tables
and figures were byte-identical to the committed ones. That check holds only
while the cache is valid, on 2026-09-18 UTC. I removed `.pytest_cache/` and
`__pycache__/`. No tracked file needed removing. `data/processed/` stays
locally, since it is gitignored and rebuilt by the pipeline.
Owner consulted: yes, the Phase 9 plan and its four decisions.

**Concepts the owner is currently learning, noted here rather than in code comments:**
- What makes a rerun reproducible and what breaks it: pinned versions,
  committed raw files and a fixed random seed make the rerun identical, and
  the one-day cache (`has_fetched_today`) is what would change the numbers
  on a later date.
- The manifest's `has_fetched_today` check is a simple date-string
  comparison, not a general-purpose cache invalidation system, worth being
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
- The persistence filter (`src/regimes.py:apply_persistence_filter()`) is
  a run-length smoothing technique, not specific to this project: collapse
  a sequence into (value, length) runs, merge any run below a minimum
  length into a neighbor, then repeat because a merge can make a run long
  enough to swallow its own next short neighbor. Worth being able to trace
  through `tests/test_regimes.py`'s hand-made label sequences by hand,
  especially the back-to-back-short-runs case, which is the one that
  actually needs the repeat-until-stable loop rather than a single pass.
- Why annualizing a short window's return produces an extreme number
  (`docs/methodology.md`'s regime-classification section, the 20-day
  `MIXED` period): the formula assumes the window's average daily
  behavior repeats for a full year, so a genuinely unusual short period
  gets compounded out to twelve months of that same behavior. This is a
  property of annualization itself, not a bug, worth being able to
  explain why the number is technically correct and still not a useful
  estimate.
- Why a correctly-computed correlation still only approximately reproduces
  a published figure (`docs/validation.md`): the math isn't the source of
  the gap, which exact instrument (GLD vs. GC=F, Composite vs.
  Nasdaq-100), which data vendor, and which exact as-of date a published
  figure used all move the number independently of any bug, and the
  Bitwise robustness-check rows are the clearest demonstration: the same
  formula, on the same day, against a different but equally reasonable
  instrument, lands an order of magnitude closer to the published value.
- Why citing secondary journalism about a research report is different
  from citing the report itself (`docs/sources.md`'s "Limitations"
  section): a news outlet's paraphrase of a number can drift from the
  original (the 0.30-vs-0.33 Bitwise Nasdaq figure is a real example of
  this), so a citation to "Outlet X, reporting Y's research" is a weaker
  and more honest claim than a citation to "Y's research" directly, and
  the two should never be written as if they were the same thing.
- Why a forward window's sum can be computed as a difference of two
  cumulative sums (`src/sentiment.py:compute_forward_log_returns()`): log
  returns add up over time, so the total return from day t+1 through day
  t+N is just (cumulative return through day t+N) minus (cumulative return
  through day t), worth tracing by hand on
  `tests/test_sentiment.py`'s 5-day example to see why this gives the same
  answer as literally summing the N days, without a reversed rolling
  window.
- Why overlapping forward-return windows inflate apparent significance
  (`docs/methodology.md`'s sentiment section): the 20-day forward return
  starting tomorrow and the 20-day forward return starting the day after
  share 19 of their 20 underlying days, so consecutive rows in
  `outputs/tables/sentiment_forward_returns_daily.csv` are not independent
  observations even though there's one row per day, a naive p-value
  would treat them as if they were, which is why this project reports n,
  mean, median, and standard deviation only, and no significance test, for
  every sentiment-bucket statistic.
- Why a random shuffled train/test split is invalid for the Phase 8
  classifier (`src/model.py`, section 6.7): regime labels are smoothed by
  a 90-day rolling window and a 15-day minimum-persistence filter, so
  they're highly autocorrelated, the label on day *t* is very likely
  the same as the label a few days before or after it. A shuffled split
  would put some post-test-date rows into training, letting the model
  train on a label from just after the point it's asked to predict, which
  is interpolation dressed up as forecasting: the reported accuracy would
  be inflated and meaningless. `TimeSeriesSplit(gap=...)` keeps every
  test fold strictly later in calendar time than everything the model
  saw in training, which is the only setup that mimics how the model
  could ever actually be used going forward from a real prediction date.
