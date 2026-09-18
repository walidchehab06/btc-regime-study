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

## Regime classification (BUILD-SPEC section 6.4)

I classify every trading day into one of four regimes, using rules on
that day's 90-day Pearson correlations, not a clustering algorithm.
Rule-based classification is deliberate: the thresholds are visible,
stated up front, and can be stress-tested, unlike whatever a clustering
algorithm decided internally.

| Regime | Condition |
|---|---|
| `RISK_ASSET` | corr(BTC, Nasdaq) >= 0.40 and corr(BTC, Nasdaq) > corr(BTC, Gold) |
| `HARD_ASSET` | corr(BTC, Gold) >= 0.35 and corr(BTC, Gold) > corr(BTC, Nasdaq) |
| `IDIOSYNCRATIC` | both correlations below 0.25 in absolute value |
| `MIXED` | anything not matching the above |

These thresholds are a starting proposal, not a fitted result, and
section 6.5's sensitivity grid exists specifically to test whether they
matter (see below).

**The persistence filter, and why it's necessary.** Applying the rule
above to every day, independently, produces labels that flicker: 79
separate runs of consecutive identical labels over the study period, with
a median run length of 7 trading days, and 63% of all runs shorter than
15 days. A regime that changes every week isn't a regime — it's noise
riding on a threshold. The persistence filter enforces a minimum: a run
only survives as its own regime period if it holds for at least 15
consecutive trading days. Shorter runs are merged into the surrounding
regime.

The one place the rule needed a decision I hadn't seen specified: when a
short run sits between two *different* regimes, which one absorbs it? I
merge a short run into the **preceding** regime — a brief blip during an
established regime doesn't rewrite what came before it. The one exception
is a short run at the very start of the series, which has no preceding
regime to merge into, so it takes on the label of the regime that follows
it instead. A merge can make a run long enough to then swallow its own
next short neighbor, so the merge step repeats until every surviving run
clears the 15-day minimum.

The filter's effect, measured directly rather than asserted:

| | Runs (regime periods) | Median run length | Day-to-day label changes |
|---|---|---|---|
| Raw (no filter) | 79 | 7 trading days | 78 (3.8% of transitions) |
| Filtered | 16 | 102 trading days | 15 (0.7% of transitions) |

The filter cuts the day-to-day flip rate by roughly 5x and turns 79 short,
noisy runs into 16 regime periods long enough to describe and reason
about. `outputs/figures/regime_label_stability_before_after.png` shows
this directly: the raw strip is visibly striped with short-lived color
changes, mostly in 2019-2020 and 2023-2024 when the Nasdaq and gold
correlations were both hovering near their thresholds; the filtered strip
underneath, over the same days, shows only 15 changes in total.
`outputs/tables/regime_label_stability_before_after.csv` has the exact
counts.

**Outputs.** The filtered regime periods are the regime timeline table
(`outputs/tables/query_09_regime_timeline.csv`, figure 3). For each
period, `outputs/tables/regime_summary_statistics.csv` reports Bitcoin's
annualized return, annualized volatility, maximum drawdown, and average
Fear & Greed level over that period's dates
(`src/core_math.py:annualized_return()`, `annualized_volatility()`,
`max_drawdown()`).

One caveat on the annualized return column specifically: annualizing a
short window exaggerates whatever happened in it, because the formula
scales a period's average daily log return up to a full year. The
20-trading-day `MIXED` period from 2020-12-14 to 2021-01-12 -- the start
of Bitcoin's late-2020 rally, when the average Fear & Greed reading was
91.7 (extreme greed) -- annualizes to a return figure in the thousands of
percent. That number is not wrong given the formula, but it isn't a
usable estimate of a typical year either; it's what compounding a single
extraordinary month out to twelve months does arithmetically. Annualized
return and volatility are more informative for the longer regime periods
(the `RISK_ASSET` period from 2022-01-11 to 2023-03-22, 300 trading days,
annualizes to -30.1%) than for anything under roughly two or three
months. See `docs/limitations.md`.

## Sensitivity analysis (BUILD-SPEC section 6.5)

The baseline thresholds above are a starting proposal, and any
threshold-based rule invites "why those numbers." I re-ran the
classification and persistence filter across every combination of the
Nasdaq threshold in {0.30, 0.35, 0.40, 0.45, 0.50} and the gold threshold
in {0.25, 0.30, 0.35, 0.40, 0.45} -- 25 combinations
(`src/regimes.py:run_sensitivity_grid()`) -- and, for each, recorded the
number of regime periods, the share of days in each regime, and whether
the most recent regime shift (baseline thresholds put its start at
2026-08-06, `RISK_ASSET` giving way to `HARD_ASSET`) still lands
somewhere in calendar year 2026.

Across all 25 combinations, a regime transition still falls in 2026. The
number of regime periods identified ranges from 13 to 17 (baseline: 16),
and `RISK_ASSET`'s share of days ranges from about 25% to 46% depending on
where the Nasdaq threshold is set -- the Nasdaq threshold has more
influence on this than the gold threshold does, visible directly in
`outputs/figures/fig05_sensitivity_heatmap.png` as the grid's stronger
gradient running left to right than top to bottom. The headline
observation -- that Bitcoin's regime shifted during 2026 -- is not an
artifact of the specific baseline threshold choice.
