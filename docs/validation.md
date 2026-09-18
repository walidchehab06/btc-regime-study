# Validation against published institutional figures

BUILD-SPEC-bitcoin-regime-study.md section 3 lists several correlation
figures that circulated in institutional research during 2026 (Grayscale,
Bitwise). Per section 3, "these figures are context, not inputs: the repo
must compute its own correlations from raw price data and then compare."
This document is that comparison. Every value below is either read
directly from `outputs/tables/validation_comparison.csv` (produced by
`src/validation.py`, Phase 6) or is one of our own already-published
Phase 4 `rolling_correlations` values -- nothing here is restated by hand.
Citations for every published figure are in `docs/sources.md`.

## Comparison table

| Published claim | Source | Published value | Published as-of | Our computed value | Series | Delta |
|---|---|---|---|---|---|---|
| BTC-Nasdaq 90-day correlation fell to ~33% | Grayscale Research (via Bloomingbit) | 0.33 | 2026-09-02 | 0.3645 | BTC_NASDAQ (^IXIC) | +0.0345 |
| BTC-gold 90-day correlation rose to ~50% | Grayscale Research (via Bloomingbit) | 0.50 | 2026-09-02 | 0.5551 | BTC_GOLD (GLD) | +0.0551 |
| BTC-gold 90-day correlation at a six-year high, ~0.50 | Bitwise (via The Block / 24-7 Wall St.) | 0.50 | 2026-08-31 | 0.5531 | BTC_GOLD (GLD) | +0.0531 |
| — same claim, gold-futures robustness check | Bitwise (via The Block / 24-7 Wall St.) | 0.50 | 2026-08-31 | 0.4932 | BTC_GOLD_GCF (GC=F) | **-0.0068** |
| BTC-Nasdaq-100 90-day correlation at a one-year low, ~0.30 | Bitwise (via The Block / 24-7 Wall St.) | 0.30 | 2026-08-31 | 0.3496 | BTC_NASDAQ (^IXIC) | +0.0496 |
| — same claim, Nasdaq-100 robustness check | Bitwise (via The Block / 24-7 Wall St.) | 0.30 | 2026-08-31 | 0.3163 | BTC_NASDAQ_NDX (^NDX) | **+0.0163** |

Full precision and every column (including `explanation`) are in
`outputs/tables/validation_comparison.csv`.

**As-of date, and a footnote on the alternative reading.** Bitwise's own
report is dated 2026-09-03 but states its Bloomberg data runs through
2026-08-31; the table above uses 2026-08-31 as the "as-of" date, since
that is the date the source's *underlying data* actually ends, not the
date the article appeared. For reference, our computed values on
2026-09-03 (the report's publish date) are BTC_GOLD = 0.5651 and
BTC_NASDAQ = 0.3782 -- close to the 08-31 readings, and the conclusions
below don't depend on which of the two dates is used.

## Reading the deltas

**Grayscale (both rows).** Our deltas are small (+0.03 to +0.06) and in
the same direction for both series, consistent with the reporting simply
being taken from a slightly different snapshot -- neither the Bloomingbit
article nor Benzinga states an exact as-of date, data vendor, or (for the
Nasdaq figure) confirms Composite vs. Nasdaq-100 beyond a title. There is
no robustness check available for these two rows, because BUILD-SPEC
section 3's known discrepancy reasons (vendor, exact date, instrument)
aren't individually confirmed anywhere in the source reporting -- the
honest conclusion is that this gap is real but not fully decomposable from
what was published.

**Bitwise gold: the robustness check is the story.** Our headline
BTC_GOLD series (GLD) overshoots the published 0.50 by +0.053. But GLD and
gold futures (GC=F) trade different hours and can diverge day to day; the
GC=F robustness check comes in at 0.493, a delta of **-0.007** -- an order
of magnitude closer to Bitwise's reported figure. This is exactly the
"spot gold vs. futures vs. GLD" reason BUILD-SPEC section 3 anticipated,
and it is directly testable rather than asserted: recomputing the same
statistic against a different instrument on the same day closes nearly
the entire gap.

**Bitwise Nasdaq: the robustness check moves the same direction.** Our
headline BTC_NASDAQ series (^IXIC, Nasdaq Composite) overshoots the
published 0.30 by +0.050. The Block's own reporting is explicit that
Bitwise's figure is computed against the **Nasdaq-100**, not the
Composite. Recomputing against ^NDX brings the delta down to **+0.016** --
again, most of the gap is explained by the named instrument difference,
not by an error in either party's methodology.

**What this validates.** Both Bitwise comparisons show the same pattern:
a published figure that looks off by 5 percentage points against our
headline series turns out to be within 1-2 points once the actual
instrument the source used is matched. That is a stronger result than a
close match by accident would have been -- it shows the discrepancy has a
specific, verifiable cause, not just "different data, who knows why."

## What is not reproduced, and why

The Grayscale and Bitwise reporting also describes a *trajectory* --
"fell from 60% to 33%," "a one-year low," "a six-year high." None of these
give a start date precise enough to compute a matching number: reproducing
"fell from 60%" would require picking some earlier date and asserting it
is the one the source used, which this repo will not do, since an invented
date used to manufacture a matching number is itself a form of
fabrication under CLAUDE.md's rules. Only the reported endpoint values --
the actual 2026 readings -- are compared above.

## Figure

Figure 10 (`outputs/figures/fig10_validation_comparison.png`) plots our
full-history 90-day BTC_NASDAQ and BTC_GOLD correlation series with the
Grayscale (2026-09-02) and Bitwise (2026-08-31) readings annotated
directly on the lines, each callout showing the published value next to
our computed value at that date.
