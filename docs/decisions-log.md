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
