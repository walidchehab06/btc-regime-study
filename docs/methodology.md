# Methodology

This document explains, in plain English, the analytical choices made by
the pipeline. Per BUILD-SPEC-bitcoin-regime-study.md section 6, everything
here is a deliberate decision, not an accident of how a merge happened to
come out. Sections are added as each phase of the pipeline is built.

## Calendar alignment (BUILD-SPEC section 6.1)

Bitcoin trades every day of the year. Nasdaq-listed equities, gold futures,
and the dollar index only trade on days the relevant exchange is open.
Correlating two series that don't share a calendar either introduces
phantom gaps or silently misaligns dates, so a deliberate rule is needed.

**The rule: the panel is restricted to the days Nasdaq (`^IXIC`) traded.**
Every other series is aligned onto that exact set of dates. Any date
Nasdaq didn't trade is dropped from the panel entirely, for every series,
including Bitcoin.

The consequence for Bitcoin: its "Monday return" is not really a one-day
return. Bitcoin's price still moved on Saturday and Sunday, but since
those dates aren't in the panel, Monday's log return is computed as
`ln(close_Monday / close_Friday)` — it silently absorbs the weekend's price
action into one multi-day figure. This is a deliberate simplification, made
explicit here rather than left as a side effect of a merge.

**Robustness check.** `panel_daily_alt_weekend.parquet` is an alternative
panel where Bitcoin's log return is computed the other way around: on
Bitcoin's own full daily calendar first (so Saturday and Sunday each get
their own one-day return), and only then aligned onto the Nasdaq calendar.
Monday's row in that panel holds only the Sunday-to-Monday return; the
weekend return is dropped rather than merged in. Every other column is
identical between the two panels, so any difference in a downstream
correlation can be attributed to this one choice. In the built panel, the
two methods disagree on 474 of 2,168 days (about 22%) — mostly Mondays,
with the remainder falling on the day after a Nasdaq holiday closes the
market for more than one day.

Timezone handling: `yfinance` returns UTC-labeled daily bars, and the
alternative.me sentiment API returns Unix timestamps. Both are converted
to UTC calendar dates before anything is merged, so a "day" means the same
thing across every source.

## Returns, not price levels (BUILD-SPEC section 6.2)

All correlations in this project use daily logarithmic returns,
`r_t = ln(P_t / P_{t-1})`, never raw prices.

Correlating price *levels* of two trending assets tends to produce
misleadingly high correlation numbers, because both series are
non-stationary — their statistical properties drift over time. Two assets
that each trend upward over years will look "correlated" purely because
they share a long-term drift, independent of whether they actually move
together on any given day. Log returns are approximately stationary and
measure the thing that actually matters for this study: does the asset
tend to move on the same days as the other one. This is a well-known
failure mode in informal crypto analysis, and naming it explicitly here is
part of what makes the project's numbers defensible.

## Forward-filling the monthly and weekly macro series (BUILD-SPEC section 5.2)

`M2SL` (M2 money supply) is published monthly; `WALCL` (Fed balance sheet)
is published weekly. The daily panel needs a value for every row, so on
days between actual releases, the last published value is carried forward.

This manufactures the appearance of daily variation out of data that only
changes once a month or once a week — plotted, it is a staircase, not a
curve. Treating those flat stretches as meaningful daily movement would be
a real analytical error: for instance, a rolling correlation computed
against a forward-filled M2 series is really being driven by a handful of
distinct M2 readings, not by genuinely independent daily observations.

To keep this honest, the panel carries a sibling `is_forward_filled_*`
boolean column next to every forward-filled value: `True` on any date that
isn't one of the series' own reported observation dates, `False` on a
genuine release date (and on dates before the series' first release, where
there is nothing to carry forward and the value is left as `NaN` instead).

## Two calendar mismatches worth naming explicitly

Building the panel surfaced two real gaps, both expected once understood,
neither a data quality problem:

- **Daily FRED series on bond-market holidays.** `DFII10`, `DTWEXBGS`, and
  `T10Y2Y` are `NaN` on Columbus Day and Veterans Day every year in the
  study period, plus a handful of other bond-market-only closures. The
  Treasury market observes holidays Nasdaq doesn't. These values are left
  as `NaN`, not filled — see docs/decisions-log.md for the tolerance this
  required in the data-integrity assertions.
- **Sentiment index, one missing day.** The Crypto Fear & Greed Index has
  no published value for 2018-04-16, a genuine gap in the source's own
  history, not a scheduled holiday. Left as `NaN` rather than forward-filled
  — sentiment isn't in BUILD-SPEC section 5.2's forward-fill list, and
  extending that list by assumption for one row wasn't worth it.

## Rolling correlations (BUILD-SPEC section 6.3)

Bitcoin's relationship to Nasdaq, gold, and the dollar index is measured
with a **rolling Pearson correlation of daily log returns** — the
correlation recomputed on a moving window of trading days, so it can
change over time instead of collapsing the whole study period into one
number. Two window lengths are computed in parallel: 30 trading days,
which reacts quickly but is noisy, and 90 trading days, which is smoother
and is the window most published institutional figures use (see
`docs/sources.md`). Neither window is allowed a partial start: the first
90-day figure needs 90 full days of returns behind it, not fewer.

**Two independent implementations of the 90-day Pearson correlation.**
Section 6.3 requires the headline 90-day figure computed twice: once by
calling pandas' own `.rolling().corr()`, and once by a function I wrote by
hand in `src/core_math.py` that computes the covariance and the two
standard deviations directly from the definition,
`corr(x, y) = cov(x, y) / (std(x) * std(y))`. The two are asserted to
agree within `1e-9` on every date before either is trusted. The point of
the hand-written version isn't that pandas is unreliable — it's that I
need to be able to explain what a correlation coefficient actually
measures, not just which library method I called.

**Spearman as a robustness check, 90-day window only.** Pearson
correlation is sensitive to outliers, and Bitcoin's return series has
extreme days. Spearman rank correlation is the standard robustness check:
instead of correlating the raw return values, it correlates their
*ranks*. Concretely, `rolling_spearman()` in `src/correlations.py` ranks
the two series' values **within each 90-day window separately** (not once
over the whole series — a value's rank depends on what else is in that
window) and then calls the same hand-written Pearson function on those
ranks. This works because Spearman correlation is, by definition, the
Pearson correlation of ranks; it avoids adding a `scipy` dependency for a
single function, and it means the same covariance-based function does
double duty. I verified this with a test the ordinary crypto data
wouldn't have caught by construction: a series `y = x**3` is a perfectly
predictable (monotonic) function of `x`, but not a linear one, so Pearson
correlation between them is high but not exactly 1.0, while Spearman —
which only sees rank order — comes out exactly 1.0. That gap is the whole
reason the two methods are reported separately.

**Three headline pairs, and which gold and dollar series.** The pairs
tracked are `BTC_NASDAQ` (BTC vs `^IXIC`), `BTC_GOLD`, and `BTC_DXY` (BTC
vs `DX-Y.NYB`, the ticker figure 1 means by "DXY"). For the gold pair, the
headline series is **`GLD`, the gold ETF, not `GC=F` gold futures** —
`GLD` trades on the same calendar the whole panel is anchored to (BUILD-
SPEC section 6.1), while `GC=F` futures trade different hours, which would
introduce a second calendar mismatch on top of the one already handled for
Bitcoin. `GC=F` remains available as the section 5.1 robustness check
against `GLD`, computed separately in the Phase 6 validation step, not
under the `BTC_GOLD` label. This was a direct question to the project
owner per BUILD-SPEC section 13 ("which gold series is the headline"), not
a default I chose silently.
