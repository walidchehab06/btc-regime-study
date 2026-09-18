# Validation against published institutional figures

BUILD-SPEC-bitcoin-regime-study.md section 3 lists correlation figures that circulated in institutional research during 2026 (Grayscale, Bitwise). The spec calls them context, not inputs. I computed my own correlations from raw price data first and then compared. Every value below comes from `outputs/tables/validation_comparison.csv` (produced by `src/validation.py`) or from the 90-day correlations stored in `rolling_correlations`. Citations for every published figure are in `docs/sources.md`.

## Comparison table

Values are rounded to two decimals, which is the precision I trust. `outputs/tables/validation_comparison.csv` has full precision and an `explanation` column for each row.

| Published claim | Source | Published value | Published as-of | My value | Series | Delta |
|---|---|---|---|---|---|---|
| BTC-Nasdaq 90-day correlation fell to about 33% | Grayscale Research (via Bloomingbit) | 0.33 | 2026-09-02 | 0.36 | BTC_NASDAQ (`^IXIC`) | +0.03 |
| BTC-gold 90-day correlation rose to about 50% | Grayscale Research (via Bloomingbit) | 0.50 | 2026-09-02 | 0.56 | BTC_GOLD (`GLD`) | +0.06 |
| BTC-gold 90-day correlation at a six-year high, about 0.50 | Bitwise (via The Block and 24/7 Wall St.) | 0.50 | 2026-08-31 | 0.55 | BTC_GOLD (`GLD`) | +0.05 |
| Same claim, gold-futures check | Bitwise (via The Block and 24/7 Wall St.) | 0.50 | 2026-08-31 | 0.49 | BTC_GOLD_GCF (`GC=F`) | -0.01 |
| BTC-Nasdaq-100 90-day correlation at a one-year low, about 0.30 | Bitwise (via The Block and 24/7 Wall St.) | 0.30 | 2026-08-31 | 0.35 | BTC_NASDAQ (`^IXIC`) | +0.05 |
| Same claim, Nasdaq-100 check | Bitwise (via The Block and 24/7 Wall St.) | 0.30 | 2026-08-31 | 0.32 | BTC_NASDAQ_NDX (`^NDX`) | +0.02 |

**As-of date.** Bitwise's report is dated 2026-09-03, but it says its Bloomberg data runs through 2026-08-31. I use 2026-08-31, because that is the date the underlying data ends. On 2026-09-03 my values are 0.57 for gold and 0.38 for Nasdaq (from `rolling_correlations`). They are close to the 08-31 readings, and the conclusions below do not depend on which date I use.

## Reading the deltas

**Grayscale, both rows.** My deltas are small (+0.03 and +0.06) and point the same way. That fits a slightly different snapshot. Neither the Bloomingbit article nor the Benzinga article states an exact as-of date or a data vendor. For the Nasdaq figure, the Benzinga title says Composite, but I could not read the article text. I have no alternate-instrument check for these two rows, because the sources do not confirm which instrument, vendor or date Grayscale used. The gap is real, and I cannot break it down from what was published.

**Bitwise gold.** My headline gold series (`GLD`) overshoots the published 0.50 by 0.05. `GLD` and gold futures (`GC=F`) trade different hours and can diverge from day to day. Recomputed with `GC=F`, my value is 0.49, a delta of -0.01. At full precision the gap shrinks from 0.053 to 0.007, about eight times smaller. This is the "spot gold versus futures versus GLD" reason the spec anticipated. I tested it by recomputing the same statistic on a different instrument for the same day.

**Bitwise Nasdaq.** My headline series (`^IXIC`, the Nasdaq Composite) overshoots the published 0.30 by 0.05. The Block reports that Bitwise's figure is computed against the Nasdaq-100, not the Composite. Recomputed with `^NDX`, the delta falls to +0.02. Most of the gap comes from the named instrument difference. I found no error in either party's method.

For both Bitwise figures, a gap of 5 points against my headline series shrinks to 1 or 2 points once I use the instrument the source used. A match by accident would have shown me nothing about why the numbers differ. Here the difference has a specific cause that I could test.

## What I did not reproduce

The Grayscale and Bitwise coverage also describes a trajectory: "fell from 60% to 33%", "a one-year low", "a six-year high". None of these gives a start date precise enough to compute a matching number. To reproduce "fell from 60%" I would have to pick an earlier date and assert that the source used it. I will not do that, because an invented date chosen to produce a matching number is a form of fabrication. I compare only the reported endpoint values, which are the actual 2026 readings.

## Figure

Figure 10 (`outputs/figures/fig10_validation_comparison.png`) plots my full-history 90-day BTC_NASDAQ and BTC_GOLD correlations. It marks the Grayscale reading (2026-09-02) and the Bitwise reading (2026-08-31) on the lines, and each callout shows the published value beside mine.
