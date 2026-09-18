# Bitcoin Cross-Asset Regime Study

Work in progress. Measuring how Bitcoin's rolling correlation with equities,
gold and the US dollar has changed since 2018, and classifying those periods
into behavioural regimes.

## Data

Raw pulls (`data/raw/`) total under 2 MB, well under the project's 50 MB
threshold, so they are committed to the repo along with `_manifest.json`,
which records the source, retrieval timestamp, row count, and date range of
every file. Run `python -m src.run_all` to reproduce or refresh them.
