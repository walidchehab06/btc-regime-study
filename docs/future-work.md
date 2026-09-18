# Future work

These are ideas I kept out of version 1. Some are outside the scope in BUILD-SPEC section 4, and some came up while building. None of them is a price forecast or a trading rule, and I do not plan to add either.

## Data

**Spot gold.** I use the GLD ETF as the headline gold series and gold futures as the check. A spot gold series would remove the trading-hours question. The free options I know of would need a new source and its own provenance record.

**A snapshot mode for reproduction.** The cache expires after one UTC day, so a later run fetches fresh data and produces different numbers. A flag that forces the committed snapshot would let anyone reproduce the exact figures in `docs/findings.md`. It would also let a run without a FRED API key succeed.

**A longer Bitcoin history.** The Fear & Greed Index starts in February 2018, and that sets the study start. The correlation and regime parts need only prices, so they could start earlier. The sentiment and model parts would stay at 2018.

**Primary sources for the published figures.** I could not reach Grayscale's own report, and the coverage of Bitwise's report disagrees on some numbers. Finding the original documents would tighten `docs/validation.md`.

## Methods

**Honest uncertainty on the sentiment results.** Block bootstrap confidence intervals, or a sample of non-overlapping windows, would give a defensible interval for the forward-return tables. I report only descriptive statistics for now because the naive intervals are too narrow.

**A second regime definition.** I chose rules over clustering so that the thresholds are visible. Fitting a hidden Markov model or a clustering model to the same correlations, and comparing its boundaries with mine, would show how much of the regime story depends on my rules.

**Descriptive attribution.** The panel already holds real yields, the broad dollar index, M2 and the Fed balance sheet. A descriptive regression of the rolling correlations on those series could ask which macro moves coincide with the shift. It would not claim cause, and the monthly and weekly series would need care because they are step functions.

**A different target for the classifier.** Regime labels are persistent by construction, so persistence wins. A target that is not built from a 90-day window, such as the sign of the next 20-day change in the correlation itself, would make a fairer test of whether the features carry any information. I would report it the same way, with the same baselines.

## Scope I decided against

On-chain measures such as hashrate, wallet flows and exchange reserves. A comparison across several cryptocurrencies. Any neural network. A live dashboard or scheduled job. Each adds a data burden or moves the project toward prediction.

## Packaging

**A Makefile or shell script.** I run Windows without `make`, so the single entry point is `python -m src.run_all`. A `Makefile` wrapping the same command would suit anyone on macOS or Linux.
