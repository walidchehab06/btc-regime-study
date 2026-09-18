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

**Concepts the owner is currently learning, noted here rather than in code comments:**
- The manifest's `has_fetched_today` check is a simple date-string
  comparison, not a general-purpose cache invalidation system — worth being
  able to explain the difference in an interview if asked "how does the
  caching work."
