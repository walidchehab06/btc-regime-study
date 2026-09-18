# BUILD SPEC — Bitcoin Cross-Asset Regime Study

**Audience: Claude Code (primary) and Claude Cowork (secondary).**
This document is the complete instruction set for building this project. Read it fully before writing any code. Where it says MUST, treat it as a hard constraint. Where it says SHOULD, use judgement but log the decision.

---

## 0. One-paragraph summary of the job

Build a reproducible Python + SQLite analysis that measures how Bitcoin's statistical relationship with other major assets (Nasdaq equities, gold, the US dollar, real interest rates) has changed over time; classifies history into behavioural "regimes" based on those relationships; checks whether market-sentiment extremes line up with regime changes; validates the computed numbers against publicly reported figures from institutional research; and ships as a documented public GitHub repository with charts and a written analysis. The project is descriptive and diagnostic. It is **not** a price-prediction system and must never be presented as one.

---

## 1. Who this is for and why that shapes every decision

The owner of this repository is **Walid Chehab**, a final-year BBA Finance student at the American University of Beirut, targeting graduate roles in Big Four Advisory/Deals and corporate finance in the Gulf. He is a **beginner in Python and SQL**, learning them in parallel with this build (Pandas, NumPy, Matplotlib, basic ML, basic SQL).

This has four consequences that override normal engineering instincts:

1. **The code exists to be explained by him in an interview.** Readability beats elegance, always. If there is a choice between a clever three-line vectorised expression and a ten-line loop-free but obvious version with named intermediate variables, choose the obvious one.
2. **He must be able to defend every number.** No output may exist that he cannot trace back to a source and a formula.
3. **Do not build a tutorial.** He is not learning *from* this repo step by step; he is learning alongside it and then reading it. Code comments explain *why a choice was made*, not *what Python syntax does*. Never write `# this is a for loop`.
4. **Nothing may be fabricated.** Not a number, not a citation, not a placeholder that looks like real data. If a data source fails, stop and report the failure. Do not generate synthetic or "example" data to keep the pipeline running, not even temporarily, unless it lives in a file explicitly named `*_synthetic_test_data.py` and is never imported by the analysis path.

---

## 2. The research question

Stated plainly, the question the repo answers is:

> **What kind of asset has Bitcoin behaved like, and when did that change?**

Broken into sub-questions the code must actually answer with numbers:

- **Q1.** How has Bitcoin's rolling correlation with Nasdaq equities, gold, and the US dollar index evolved over the study period?
- **Q2.** Can that history be divided into distinct, persistent behavioural regimes ("trades like a risk asset", "trades like gold / a debasement hedge", "trades on its own")?
- **Q3.** How long do those regimes last, how often do they flip, and how much does the answer depend on the thresholds chosen?
- **Q4.** Do market-sentiment extremes (Crypto Fear & Greed Index) cluster around regime transitions, or around forward returns?
- **Q5.** Can a simple, interpretable model classify the *next* regime better than the naive "tomorrow looks like today" baseline? (The honest answer may well be **no** — see §9.)

The project succeeds if it answers all five with defensible numbers, **including where the answer is negative or inconclusive.**

---

## 3. Why this topic, and the external context to validate against

As of September 2026 there is a live institutional debate about whether Bitcoin is decoupling from technology equities and re-coupling with gold. Published figures that circulated in 2026 include:

- Grayscale Research reporting Bitcoin's 90-day correlation with the Nasdaq Composite falling from roughly 60% to about 33%, while its correlation with gold rose from near zero to around 50%.
- Bitwise reporting the 90-day Bitcoin–gold correlation at a multi-year high (variously reported as a six-year and nine-year high depending on the measure and date), with one widely quoted reading around 0.56, and the Bitcoin–Nasdaq correlation at a one-year low around 0.30.
- Commentary tying the shift to the "debasement trade": US gross federal debt passing roughly $40 trillion in August 2026 and a projected fiscal 2026 deficit near $1.9 trillion.

**These figures are context, not inputs.** The repo MUST compute its own correlations from raw price data and then compare. Every externally sourced number that appears in any written deliverable MUST carry a citation with publisher, title, URL, and the date it was accessed, collected in `docs/sources.md`. If a number cannot be sourced to a named publisher, it does not go in the write-up.

A dedicated deliverable, `docs/validation.md`, MUST reproduce the comparison and explain any discrepancy. Expect discrepancies. Known legitimate reasons a self-computed figure differs from a published one:

- Nasdaq Composite (`^IXIC`) vs Nasdaq 100 (`^NDX`)
- Spot gold vs gold futures (`GC=F`) vs the GLD ETF
- Correlation of **returns** vs correlation of **price levels** (these are very different; this repo uses returns — see §6.3)
- Different window lengths (30-day vs 90-day) and calendar vs trading days
- Different end dates
- Whether weekend Bitcoin moves are included or dropped

Explaining a discrepancy correctly is a stronger result than matching by accident. Say so in the document.

---

## 4. Scope boundaries — what this project is NOT

Do not build, and do not let scope drift toward:

- A price-prediction model, a trading bot, a backtested strategy with P&L, or anything producing a buy/sell signal.
- A live/streaming dashboard, a web app, a deployed service, or a scheduled job.
- A deep-learning model of any kind. No LSTM, no transformer, no neural network.
- A multi-cryptocurrency comparison. Bitcoin only.
- On-chain analytics (hashrate, wallet flows, exchange reserves). Interesting, but out of scope for v1 and adds a data-sourcing burden.
- Anything requiring a paid data subscription.

If any of these look tempting mid-build, write the idea into `docs/future-work.md` and move on.

---

## 5. Data sources — exact specification

All sources are free and public. Fetch once, cache to disk, and never re-fetch during analysis. Every cached file MUST record the UTC timestamp of retrieval.

### 5.1 Market prices — `yfinance`

| Series | Ticker | Role in the analysis |
|---|---|---|
| Bitcoin | `BTC-USD` | The subject |
| Nasdaq Composite | `^IXIC` | Risk-asset / tech-equity benchmark |
| Nasdaq 100 | `^NDX` | Secondary equity benchmark, used for the validation comparison |
| Gold futures | `GC=F` | Hard-asset benchmark |
| Gold ETF | `GLD` | Robustness check against `GC=F` (different trading hours) |
| US Dollar Index | `DX-Y.NYB` | Dollar-strength driver |
| S&P 500 | `^GSPC` | Broad-equity control |
| Volatility index | `^VIX` | Risk-sentiment control |

Pull daily OHLCV, `auto_adjust=True`, from **2018-02-01** (the start of the Fear & Greed Index history, so all series share a common start) through the run date.

Ticker symbols drift. If any ticker returns empty, do not silently substitute — fail loudly, log it, and surface it to the user with a suggested alternative.

### 5.2 Macro — FRED API (Federal Reserve Bank of St. Louis)

Requires a free API key. Store in a `.env` file; `.env` MUST be in `.gitignore`. Provide `.env.example` with the variable name and no value.

| Series ID | What it is | Why it matters |
|---|---|---|
| `DFII10` | 10-year Treasury inflation-indexed (real) yield | The opportunity cost of holding a non-yielding asset; the classic driver of gold |
| `DTWEXBGS` | Nominal Broad US Dollar Index | Official dollar measure; cross-check on `DX-Y.NYB` |
| `M2SL` | M2 money supply (monthly) | The "liquidity" thesis; monthly, so must be forward-filled — document this |
| `WALCL` | Fed balance sheet, total assets (weekly) | Liquidity proxy; weekly, forward-fill |
| `T10Y2Y` | 10y–2y Treasury spread | Macro-cycle control |

FRED series have publication lags and revisions. Record the vintage date. Forward-filling lower-frequency series into a daily panel is acceptable **only if explicitly documented** in `docs/methodology.md` with a note that it creates a step function, not smooth daily variation.

### 5.3 Sentiment — Crypto Fear & Greed Index

- Endpoint: `https://api.alternative.me/fng/?limit=0&format=json`
- No API key. Returns daily values from 1 February 2018 to present, scored 0–100 with a text label (Extreme Fear → Extreme Greed).
- This is a composite index built by a third party from volatility, volume, social media, dominance and trends. The repo MUST state in `docs/data-dictionary.md` that its exact construction is proprietary and not independently verifiable, and that this is a limitation.
- Read the API's own documentation on the returned fields before parsing. Do not assume field names.

### 5.4 Caching and provenance rules

- Raw pulls land in `data/raw/` as CSV or Parquet, named `{source}_{series}_{YYYYMMDD}.csv`.
- A machine-readable `data/raw/_manifest.json` records, for each file: source, series identifier, retrieval timestamp (UTC), row count, first and last date, and the library version used.
- Raw data files are committed to the repo **only if** total size stays under ~50 MB; otherwise commit the manifest and a `scripts/fetch_all.py` that regenerates them. State which choice was made in the README.
- `data/processed/` holds the cleaned panel and the SQLite database. Never edit raw files in place.

---

## 6. Methodology — the analytical core

Everything in this section MUST also appear, in plain English, in `docs/methodology.md`. That document is what makes the project credible; treat it as a first-class deliverable, not an afterthought.

### 6.1 The calendar alignment problem

Bitcoin trades 24/7/365. Equities, gold futures and the dollar index do not. Any correlation between them requires a decision about what to do with Bitcoin's weekend and holiday moves.

**Rule: restrict the panel to days on which the Nasdaq traded** (inner join on `^IXIC` dates). Bitcoin's return on a Monday is then the return from the previous Friday's close to Monday's close — a multi-day return covering the weekend.

This MUST be:
- implemented explicitly, not as an accidental side effect of a merge;
- documented as a deliberate choice;
- accompanied by a robustness check. Build one alternative panel where Bitcoin returns are sampled at the same daily frequency but weekend returns are dropped rather than absorbed, and report whether the headline correlations change materially.

Timezone note: `yfinance` daily bars and the Fear & Greed API use different conventions. Normalise everything to UTC calendar dates and say so.

### 6.2 Returns, not prices

All correlations MUST use **daily logarithmic returns**: `r_t = ln(P_t / P_{t-1})`.

Reason to state in the docs: correlating price *levels* of two trending assets produces spuriously high correlations, because both are non-stationary. Two assets that each drift upward will appear correlated even with unrelated day-to-day behaviour. Returns are approximately stationary and are what practitioners actually use. This is one of the most common analytical errors in amateur crypto analysis, and naming it explicitly is part of the project's value.

### 6.3 Rolling correlation

- Pearson correlation on daily log returns.
- Windows: **30 trading days** and **90 trading days**, computed in parallel. 90-day is the headline (it matches most published institutional figures); 30-day is shown to demonstrate how much window choice matters.
- Minimum observations equal to the full window; no partial windows at the start of the series.
- Implement the 90-day rolling correlation **twice**: once with Pandas `.rolling().corr()`, and once with a hand-written NumPy function computing covariance and standard deviations directly. Assert the two agree to within a small numerical tolerance and keep both in the repo, with the hand-written version in `src/core_math.py`. Rationale: the owner needs to be able to explain what a correlation coefficient *is*, not merely which method he called.
- Also compute **Spearman rank correlation** for the 90-day window as a robustness check, since Pearson is sensitive to outliers and crypto has extreme days. Report where Pearson and Spearman disagree notably.

### 6.4 Regime classification

Regimes are defined by rules on the 90-day correlations, not by a clustering algorithm. Rule-based is deliberate: it is transparent, explainable, and the thresholds can be stress-tested.

Baseline definition (these numbers are a **starting proposal** and MUST be tested for sensitivity, see §6.5):

| Regime | Condition |
|---|---|
| `RISK_ASSET` | corr(BTC, Nasdaq) ≥ 0.40 **and** corr(BTC, Nasdaq) > corr(BTC, Gold) |
| `HARD_ASSET` | corr(BTC, Gold) ≥ 0.35 **and** corr(BTC, Gold) > corr(BTC, Nasdaq) |
| `IDIOSYNCRATIC` | both correlations below 0.25 in absolute value |
| `MIXED` | anything not matching the above |

**Persistence filter:** a regime label only counts as a regime if it holds for at least **15 consecutive trading days**. Shorter runs are relabelled to the surrounding regime. Without this, the labels flicker day to day and the whole concept becomes noise. Document the filter and show a before/after chart of label stability.

Outputs required: a regime timeline table (start date, end date, duration in trading days, regime), summary statistics per regime (Bitcoin's annualised return, annualised volatility, maximum drawdown, average Fear & Greed level within each regime), and a stacked timeline chart.

### 6.5 Sensitivity analysis — mandatory

Any threshold-based classification invites the question "why those numbers?". Answer it before it is asked.

Produce a sensitivity grid: vary the Nasdaq threshold across {0.30, 0.35, 0.40, 0.45, 0.50} and the gold threshold across {0.25, 0.30, 0.35, 0.40, 0.45}, and for each combination report the number of regimes identified, the share of days in each regime, and whether the headline conclusion (that a shift occurred during 2026) survives. Present as a heatmap plus a short paragraph of interpretation.

If the conclusion does **not** survive across most of the grid, say that clearly in the write-up. That finding is more valuable than a fragile positive result.

### 6.6 Sentiment analysis

- Merge the Fear & Greed Index into the daily panel.
- Define extremes: value ≤ 20 ("extreme fear") and ≥ 80 ("extreme greed"). State that these are the index publisher's conventional bands.
- Compute forward returns from each day: 1, 5, 20, and 60 trading days ahead.
- Report mean and median forward returns conditional on the sentiment bucket, **with sample sizes and a measure of dispersion**. A mean forward return quoted without n and standard deviation is not a result, it is a talking point.
- Overlapping forward-return windows are statistically correlated with each other. This inflates apparent significance. The docs MUST acknowledge this explicitly and, if any statistical test is run, note that naive p-values will be too optimistic. Preferred handling: report descriptive statistics and confidence intervals with an explicit caveat, rather than claiming significance.
- Cross-tabulate sentiment bucket against regime label. Ask whether extremes cluster near transitions.

### 6.7 The machine-learning component

Deliberately small, interpretable, and honestly evaluated.

- **Task:** multi-class classification of the regime label **5 trading days ahead**.
- **Models:** logistic regression (multinomial) and a decision tree with `max_depth` capped between 3 and 5 so the tree can be drawn and read. Nothing else.
- **Features** (all must be computable using only information available on the prediction date — no look-ahead):
  - current 30-day and 90-day correlations with Nasdaq, gold, DXY
  - 20-day realised volatility of Bitcoin
  - Fear & Greed level and its 14-day change
  - 20-day change in DXY and in the 10-year real yield
  - 20-day Bitcoin momentum
  - current regime label (one-hot encoded)
- **Validation:** `TimeSeriesSplit` or an explicit expanding-window walk-forward. **Never** a random shuffled train/test split. State in the docs why shuffling time series is invalid: it lets the model train on the future and test on the past, which produces impressive and meaningless scores.
- **Baselines that MUST be reported alongside the model:**
  1. Persistence: predict that the regime in 5 days equals today's regime.
  2. Majority class: always predict the most common regime in the training window.
- **Scoring:** accuracy, balanced accuracy, macro F1, and a confusion matrix. Classes will be imbalanced; report class support.
- **The honesty requirement:** the persistence baseline will probably be hard to beat, because regimes are persistent by construction (they are built from 90-day rolling windows and filtered for 15-day minimum runs, so tomorrow is nearly always today). If the model does not beat it, `docs/findings.md` MUST say so plainly, in the headline, and explain *why* this is the expected result given how the target was constructed. Do not tune until something looks good. Do not quietly drop the baseline. A student who correctly explains why his model failed to beat a naive baseline demonstrates more competence than one reporting 97% accuracy on a leaked target.
- Add a short `docs/ml-caveats.md` covering: target leakage risk from overlapping windows, why accuracy is a weak metric under class imbalance, and why this model is exploratory rather than actionable.

---

## 7. Repository structure

```
btc-regime-study/
├── README.md
├── requirements.txt
├── .env.example
├── .gitignore
├── Makefile                     # or run.sh — one command to reproduce everything
├── data/
│   ├── raw/                     # cached API pulls + _manifest.json
│   └── processed/
│       ├── panel_daily.parquet
│       └── btc_regime.db        # SQLite
├── src/
│   ├── config.py                # dates, tickers, thresholds, window lengths — ALL tunables here
│   ├── fetch_market.py          # yfinance pulls
│   ├── fetch_fred.py            # FRED pulls
│   ├── fetch_sentiment.py       # Fear & Greed pull
│   ├── build_panel.py           # merge, align calendars, compute returns
│   ├── core_math.py             # hand-written correlation / volatility / drawdown functions
│   ├── correlations.py          # rolling correlations, both implementations, Spearman
│   ├── regimes.py               # classification rules + persistence filter + sensitivity grid
│   ├── sentiment.py             # forward returns, bucket statistics
│   ├── model.py                 # logistic regression, decision tree, walk-forward, baselines
│   ├── database.py              # SQLite schema creation + loading
│   └── charts.py                # every figure, one function per figure
├── sql/
│   ├── schema.sql
│   └── analysis_queries.sql     # the questions answered in SQL, each with a comment explaining it
├── notebooks/
│   └── exploration.ipynb        # optional, clearly marked as scratch work
├── outputs/
│   ├── figures/                 # PNG, 150+ dpi
│   └── tables/                  # CSV of every number quoted in the write-up
└── docs/
    ├── methodology.md
    ├── data-dictionary.md
    ├── validation.md
    ├── findings.md
    ├── limitations.md
    ├── ml-caveats.md
    ├── sources.md
    ├── future-work.md
    └── decisions-log.md
```

---

## 8. The SQLite layer — make it real, not decorative

SQL must do actual analytical work, not merely store a dataframe. A reviewer should see queries that answer questions.

**Schema (`sql/schema.sql`):**

- `prices_daily(date, ticker, close, volume)` — long format, primary key `(date, ticker)`
- `returns_daily(date, ticker, log_return)`
- `macro_daily(date, series_id, value, is_forward_filled)` — the boolean flag matters for honesty
- `sentiment_daily(date, fng_value, fng_label)`
- `rolling_correlations(date, pair, window, method, correlation)` — `pair` like `'BTC_NASDAQ'`, `method` in `('pearson','spearman')`
- `regimes(date, regime_label, regime_id)` and `regime_periods(regime_id, regime_label, start_date, end_date, n_days)`
- Indexes on `date` for every table.

**`sql/analysis_queries.sql` MUST include at least these, each preceded by a comment stating the question in English:**

1. Average 90-day BTC–Nasdaq and BTC–gold correlation by calendar year.
2. The 20 days with the largest single-day change in the 90-day BTC–gold correlation, with the Fear & Greed value on each.
3. Bitcoin's average forward 20-day return grouped by Fear & Greed bucket, with counts.
4. Duration and count of each regime type, ordered by length.
5. Days where BTC–Nasdaq correlation and BTC–gold correlation crossed over, listed chronologically.
6. Per-regime annualised volatility of Bitcoin computed in SQL.
7. A join proving that the correlation values stored in SQLite match those computed in Pandas (a reconciliation query).

Query results are exported to `outputs/tables/` so every number in the write-up has a file behind it.

---

## 9. Figures required

One function per figure in `src/charts.py`. Matplotlib only (no seaborn, no plotly) so the owner learns one library well.

1. **Rolling 90-day correlations over time** — BTC vs Nasdaq, gold, DXY on one panel, with a horizontal zero line and shaded bands marking regimes.
2. **30-day vs 90-day correlation, same pair** — to show window sensitivity visually.
3. **Regime timeline** — a coloured horizontal band across the study period with Bitcoin's price on a log scale above it.
4. **Correlation heatmap** of all assets' returns over the full period and over the most recent 90 days, side by side.
5. **Sensitivity heatmap** from §6.5.
6. **Fear & Greed over time** with extreme bands shaded, overlaid on Bitcoin price.
7. **Forward-return distributions by sentiment bucket** — box plots or violins with n annotated on each.
8. **Confusion matrix** for the classifier, next to the persistence baseline's confusion matrix.
9. **Decision tree plot** (`sklearn.tree.plot_tree`), readable at depth ≤ 5.
10. **Validation chart** — self-computed 90-day BTC–Nasdaq and BTC–gold correlations with annotated markers at the dates of the publicly reported figures.

Chart style rules: no chartjunk, no 3D, no default rainbow colormaps for sequential data, axis labels with units, a caption line stating the data source and date range, and a consistent palette defined once in `charts.py`. Every figure must be legible in greyscale.

---

## 10. Writing style — avoiding the "AI-generated" tell

The written deliverables are judged by humans who read a lot of AI output. The following rules are not stylistic preferences; they are credibility requirements.

**Do not:**
- Use emoji anywhere, including the README.
- Open sections with "In today's fast-paced financial landscape" or similar throat-clearing.
- Use "delve", "leverage" as a verb, "robust" as filler, "seamless", "cutting-edge", "game-changing", "unlock", "harness", "landscape", "realm", "testament to".
- Use the "It's not just X, it's Y" construction.
- Use em-dash asides as a rhythmic tic.
- Write a bulleted list where two sentences would do.
- End sections with a summarising flourish that repeats what was just said.
- Claim significance, edge, or predictive power anywhere.
- Round numbers to look neat. If the correlation is 0.3271, write 0.33 and say the precision is two decimals.

**Do:**
- Write short declarative sentences.
- State the number, then the caveat, then move on.
- Use first person singular in the write-up ("I chose a 90-day window because...") — this is a personal project and the author is a person.
- Flag uncertainty where it exists, in the same sentence as the claim.
- Keep the README under roughly 600 words: what the project does, what data it uses, how to run it, the three headline findings, and where the detail lives. Everything else goes in `docs/`.

---

## 11. Code style rules

- Python 3.11+. Pandas, NumPy, Matplotlib, scikit-learn, yfinance, requests, python-dotenv, and the standard library `sqlite3`. Nothing else without asking.
- Functions, not classes, unless state genuinely needs holding. No abstract base classes, no dependency injection, no plugin architecture.
- Every function gets a docstring with: one line on what it does, one line on why it exists in this project, the parameters, and what it returns. Where the function implements a concept from `docs/methodology.md`, reference the section.
- Named intermediate variables over chained one-liners. `btc_daily_log_returns` beats `df.iloc[:,0].pct_change().apply(np.log1p)` buried in an argument.
- All tunable parameters live in `src/config.py`. No magic numbers in analysis code. Changing the correlation window must require editing exactly one line.
- Assertions at data-integrity boundaries: after every merge, assert the row count and date range are what was expected; assert no duplicate dates; assert no unexpected NaNs. Fail loudly.
- Log to stdout what is happening at each pipeline step, including row counts before and after each join. Silent data loss is the most common failure mode in this kind of project.
- A `tests/` folder with a handful of real tests: that the hand-written correlation matches Pandas on known input; that a synthetic series with known correlation returns the right value; that the persistence filter behaves correctly on a hand-made label sequence; that no NaN survives into the modelling dataset.
- Deterministic: set random seeds, pin versions in `requirements.txt`.

---

## 12. Build order and acceptance criteria

Work in this order. Do not start a phase until the previous one's criteria are met. Commit at the end of each phase with a clear message.

**Phase 1 — Data acquisition**
Build the three fetch modules and the manifest.
*Done when:* all series pull successfully, the manifest is populated, row counts and date ranges are printed and sane, and re-running uses the cache rather than re-hitting the APIs.

**Phase 2 — Panel construction**
Merge, align calendars per §6.1, compute log returns, handle the forward-fill of monthly and weekly macro series with the flag column.
*Done when:* `panel_daily.parquet` exists, there are no unexplained NaNs, the alternative weekend-handling panel also builds, and a printed summary shows date range, row count, and per-column null counts.

**Phase 3 — SQLite**
Create the schema, load the panel, write the analysis queries.
*Done when:* the reconciliation query (§8.7) passes and all seven queries return results written to `outputs/tables/`.

**Phase 4 — Correlations**
Both implementations, both windows, Pearson and Spearman.
*Done when:* the two implementations agree within tolerance, the assertion test passes, and figures 1, 2 and 4 render.

**Phase 5 — Regimes**
Classification, persistence filter, timeline, per-regime statistics, sensitivity grid.
*Done when:* `regime_periods` is populated with plausible, non-flickering periods, and figures 3 and 5 render.

**Phase 6 — Validation**
Reproduce the published comparisons, write `docs/validation.md` with the deltas and explanations.
*Done when:* every externally quoted figure has a computed counterpart, a stated difference, and a reason.

**Phase 7 — Sentiment**
Forward returns, buckets, cross-tabs, figures 6 and 7.
*Done when:* every reported statistic carries n and a dispersion measure.

**Phase 8 — Model**
Features, walk-forward split, both models, both baselines, figures 8 and 9.
*Done when:* the baseline comparison is reported honestly whichever way it goes.

**Phase 9 — Documentation and packaging**
All `docs/` files, README, Makefile, tests passing, repo cleaned of scratch files.
*Done when:* a clean clone plus `make all` reproduces every figure and table from scratch.

---

## 13. Interaction protocol with the owner

- **Ask before assuming** on anything that changes the meaning of a result: threshold choices, study start date, which gold series is the headline, how to handle a data gap.
- **Do not ask** about naming, file layout, or implementation detail already specified here. Decide and log it.
- Maintain `docs/decisions-log.md`: date, decision, alternatives considered, reason, and whether the owner was consulted. This file is a genuine differentiator in a portfolio project and also the owner's revision aid.
- After each phase, produce a short plain-English summary of what was built, what the numbers say, and anything surprising or suspicious in the data.
- When a result looks too good, say so and investigate before reporting it.
- Where a concept in the code is one the owner is currently learning (rolling windows, joins, train/test splitting, class imbalance), add a one-line pointer in `docs/decisions-log.md` rather than expanding the code comments into a lesson.

---

## 14. Absolute prohibitions

1. Never invent a data point, a correlation value, a citation, or a source URL.
2. Never present the model as predictive of Bitcoin's price or as a trading signal.
3. Never remove a baseline, a caveat, or a negative result to make the project look stronger.
4. Never shuffle time-series data in cross-validation.
5. Never commit the `.env` file or any API key.
6. Never write a README claim the repository does not substantiate with a file.
7. If a required data source is unavailable, stop and report. Do not substitute a different asset silently.

---

## 15. Definition of done for the whole project

The project is finished when all of the following are true:

- A clean clone of the repo, with a FRED key supplied, reproduces every figure and table with one command.
- `docs/findings.md` states three to five findings, each with a number, a figure reference, and a caveat.
- `docs/validation.md` compares self-computed correlations to at least three published institutional figures with explained deltas.
- `docs/limitations.md` honestly lists what this analysis cannot tell you, including: correlation is not causation; regime labels are constructed, not observed; the Fear & Greed Index is a proprietary composite; overlapping windows inflate apparent significance; one asset over eight years is a small sample of macro regimes.
- The owner can, without notes, explain the calendar alignment choice, why returns rather than prices, what a 90-day rolling Pearson correlation measures, how the regime rules work, why the persistence filter exists, why shuffled cross-validation would be invalid, and what the model result actually shows.

That last criterion is the one that matters most. If the code is finished and the owner cannot do that, the project is not done.
