"""
Every figure the project produces, one function per figure, per
BUILD-SPEC-bitcoin-regime-study.md section 9 and section 12 (Phase 4 for
figures 1, 2, and 4; later phases add the rest).

Why this file exists: section 9 requires matplotlib only (no seaborn, no
plotly), one consistent palette defined once, and every figure legible in
greyscale -- this module is that one place the palette and shared chart
conventions live, so every figure looks like it came from the same study.
"""

import sys

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import sqlite3

from src import config

# --- Palette, defined once (BUILD-SPEC section 9) ---
# Categorical colors are the first three slots of a colorblind-validated
# eight-hue sequence (blue, orange, aqua) -- chosen because with exactly
# three series on screen together, these three clear both the color-vision-
# deficiency and normal-vision separation checks pairwise, not just
# adjacent-in-a-list. Paired with a distinct linestyle per pair so identity
# never depends on color alone (the greyscale/print requirement).
PAIR_COLORS = {
    "BTC_NASDAQ": "#2a78d6",  # blue
    "BTC_GOLD": "#eb6834",  # orange
    "BTC_DXY": "#1baf7a",  # aqua
}
PAIR_LINESTYLES = {
    "BTC_NASDAQ": "-",
    "BTC_GOLD": "--",
    "BTC_DXY": ":",
}
PAIR_LABELS = {
    "BTC_NASDAQ": "BTC vs Nasdaq Composite (^IXIC)",
    "BTC_GOLD": "BTC vs Gold (GLD)",
    "BTC_DXY": "BTC vs US Dollar Index (DX-Y.NYB)",
}

# Diverging pair (blue <-> red, neutral gray midpoint) for the correlation
# heatmap: correlation runs from -1 to +1, a polarity, not a magnitude, so
# a sequential single-hue ramp would be the wrong encoding.
DIVERGING_COLORMAP = "RdBu_r"  # red at -1, white/gray at 0, blue at +1

TEXT_PRIMARY = "#0b0b0b"
TEXT_SECONDARY = "#52514e"
GRIDLINE = "#e1e0d9"
BASELINE = "#c3c2b7"

plt.rcParams["font.family"] = "sans-serif"
plt.rcParams["axes.edgecolor"] = BASELINE
plt.rcParams["axes.labelcolor"] = TEXT_PRIMARY
plt.rcParams["xtick.color"] = TEXT_SECONDARY
plt.rcParams["ytick.color"] = TEXT_SECONDARY
plt.rcParams["text.color"] = TEXT_PRIMARY


def save_figure(fig, filename):
    """
    Save a figure to outputs/figures/ at the project's standard DPI.

    Why it exists: every figure function ends the same way; keeping the
    save call in one place is what makes config.FIGURE_DPI a true
    single-line tunable (section 11).

    Parameters:
        fig: matplotlib.figure.Figure.
        filename: str, e.g. "fig01_rolling_correlations_overview.png".

    Returns:
        pathlib.Path, the path the figure was saved to.
    """
    config.OUTPUTS_FIGURES_DIR.mkdir(parents=True, exist_ok=True)
    output_path = config.OUTPUTS_FIGURES_DIR / filename
    fig.savefig(output_path, dpi=config.FIGURE_DPI, bbox_inches="tight")
    plt.close(fig)
    print(f"[charts] saved {output_path}")
    return output_path


def add_caption(fig, text):
    """
    Add the section 9-required caption line (data source and date range)
    below a figure.

    Why it exists: section 9 requires every figure to carry a caption
    stating the data source and date range, so a reader never has to guess
    what a chart is drawn from.

    Parameters:
        fig: matplotlib.figure.Figure.
        text: str, the caption line.

    Returns:
        None.
    """
    fig.text(0.01, -0.02, text, ha="left", va="top", fontsize=8, color=TEXT_SECONDARY)


def load_rolling_correlations_wide(conn, window, method, pairs):
    """
    Load rolling_correlations rows for one window/method into a wide
    DataFrame, one column per pair.

    Why it exists: sql/schema.sql stores correlations long (one row per
    date/pair/window/method), which is right for SQL aggregation but not
    for plotting several pairs' lines on one axis, which wants one column
    per pair the way build_panel.py's wide panel does.

    Parameters:
        conn: sqlite3.Connection, open connection to btc_regime.db.
        window: int, 30 or 90.
        method: str, 'pearson' or 'spearman'.
        pairs: list of str, pair labels to include, e.g.
            list(config.CORRELATION_PAIRS).

    Returns:
        pandas.DataFrame indexed by date (datetime), one column per pair
        in pairs, values are the correlation.
    """
    placeholders = ",".join("?" for _ in pairs)
    query = (
        "SELECT date, pair, correlation FROM rolling_correlations "
        f"WHERE window = ? AND method = ? AND pair IN ({placeholders})"
    )
    long_df = pd.read_sql_query(query, conn, params=[window, method, *pairs])
    long_df["date"] = pd.to_datetime(long_df["date"])
    wide_df = long_df.pivot(index="date", columns="pair", values="correlation").sort_index()
    print(f"[charts] loaded {len(long_df)} rolling_correlations rows ({method}, {window}d) -> wide {wide_df.shape}")
    return wide_df


def plot_rolling_correlations_overview(correlations_wide, regime_periods=None, filename="fig01_rolling_correlations_overview.png"):
    """
    Figure 1: BTC's 90-day Pearson correlation with Nasdaq, gold, and DXY
    on one panel, with a zero line.

    Why it exists: BUILD-SPEC section 9, figure 1 -- the headline chart of
    the whole study.

    Parameters:
        correlations_wide: pandas.DataFrame indexed by date, one column
            per pair (config.CORRELATION_PAIRS keys), from
            load_rolling_correlations_wide() at window=90, method='pearson'.
        regime_periods: pandas.DataFrame with start_date/end_date/regime_label
            columns, or None. Regime classification is built in Phase 5;
            this figure renders without the shaded bands until then and is
            regenerated once regime_periods exists -- see
            docs/decisions-log.md.
        filename: str, output filename under outputs/figures/.

    Returns:
        pathlib.Path, the saved figure's path.
    """
    fig, ax = plt.subplots(figsize=(10, 5))

    for pair in correlations_wide.columns:
        ax.plot(
            correlations_wide.index,
            correlations_wide[pair],
            label=PAIR_LABELS.get(pair, pair),
            color=PAIR_COLORS.get(pair, TEXT_PRIMARY),
            linestyle=PAIR_LINESTYLES.get(pair, "-"),
            linewidth=1.5,
        )

    ax.axhline(0, color=BASELINE, linewidth=1, zorder=0)

    if regime_periods is not None and len(regime_periods) > 0:
        # Placeholder for Phase 5: shaded bands per regime_periods row go here.
        pass

    ax.set_ylim(-1.0, 1.0)
    ax.set_xlabel("Date")
    ax.set_ylabel("90-day Pearson correlation of daily log returns (unitless, -1 to 1)")
    ax.set_title("Bitcoin's rolling 90-day correlation with Nasdaq, gold, and the dollar index")
    ax.grid(True, color=GRIDLINE, linewidth=0.5)
    ax.legend(loc="upper left", frameon=False)

    date_range = f"{correlations_wide.index.min().date()} to {correlations_wide.index.max().date()}"
    add_caption(
        fig,
        f"Source: yfinance (BTC-USD, ^IXIC, GLD, DX-Y.NYB), daily log returns, {date_range}. "
        "90-day window, no partial windows.",
    )

    return save_figure(fig, filename)


def plot_window_sensitivity(correlations_30d, correlations_90d, pair_label, filename="fig02_window_sensitivity.png"):
    """
    Figure 2: 30-day vs 90-day Pearson correlation, same pair, to show how
    much the window-length choice matters.

    Why it exists: BUILD-SPEC section 9, figure 2.

    Parameters:
        correlations_30d: pandas.Series indexed by date, the 30-day Pearson
            correlation for config.WINDOW_SENSITIVITY_PAIR.
        correlations_90d: pandas.Series indexed by date, the 90-day Pearson
            correlation for the same pair.
        pair_label: str, the pair these two series are for (for the title
            and caption, e.g. config.WINDOW_SENSITIVITY_PAIR).
        filename: str, output filename under outputs/figures/.

    Returns:
        pathlib.Path, the saved figure's path.
    """
    fig, ax = plt.subplots(figsize=(10, 4.5))

    ax.plot(
        correlations_30d.index,
        correlations_30d.values,
        label=f"{config.CORRELATION_WINDOW_SHORT}-day window",
        color=PAIR_COLORS.get(pair_label, "#2a78d6"),
        linestyle="-",
        linewidth=1.2,
        alpha=0.8,
    )
    ax.plot(
        correlations_90d.index,
        correlations_90d.values,
        label=f"{config.CORRELATION_WINDOW_HEADLINE}-day window",
        color=TEXT_PRIMARY,
        linestyle="--",
        linewidth=1.8,
    )

    ax.axhline(0, color=BASELINE, linewidth=1, zorder=0)
    ax.set_ylim(-1.0, 1.0)
    ax.set_xlabel("Date")
    ax.set_ylabel("Pearson correlation of daily log returns (unitless, -1 to 1)")
    ax.set_title(f"Window-length sensitivity: {PAIR_LABELS.get(pair_label, pair_label)}")
    ax.grid(True, color=GRIDLINE, linewidth=0.5)
    ax.legend(loc="upper left", frameon=False)

    date_range = f"{correlations_90d.index.min().date()} to {correlations_90d.index.max().date()}"
    add_caption(
        fig,
        f"Source: yfinance, daily log returns, {date_range}. "
        f"Same pair, two window lengths, both with no partial windows.",
    )

    return save_figure(fig, filename)


def plot_correlation_heatmap(panel, log_return_columns, column_labels, filename="fig04_correlation_heatmap.png"):
    """
    Figure 4: correlation heatmap of all assets' daily log returns, full
    study period and most recent 90 trading days, side by side.

    Why it exists: BUILD-SPEC section 9, figure 4. Computed directly from
    the panel with pandas' own .corr(), independent of rolling_correlations
    -- this is a static snapshot, not a time series.

    Parameters:
        panel: pandas.DataFrame, the primary daily panel (panel_daily.parquet).
        log_return_columns: list of str, the log_return_<ticker> columns to
            include, e.g. [f"log_return_{t}" for t in config.MARKET_TICKERS].
        column_labels: dict, log_return_<ticker> -> short display label
            (e.g. "BTC", "Nasdaq Comp.") for the heatmap's tick labels.
        filename: str, output filename under outputs/figures/.

    Returns:
        pathlib.Path, the saved figure's path.
    """
    returns = panel[log_return_columns].dropna()
    full_period_corr = returns.corr(method="pearson")
    recent_90d_corr = returns.tail(config.CORRELATION_WINDOW_HEADLINE).corr(method="pearson")

    labels = [column_labels[col] for col in log_return_columns]

    fig, axes = plt.subplots(1, 2, figsize=(13, 5.5))
    fig.subplots_adjust(wspace=0.6)
    panels = [
        (axes[0], full_period_corr, f"Full period ({returns.index.min().date()} to {returns.index.max().date()})"),
        (
            axes[1],
            recent_90d_corr,
            f"Most recent {config.CORRELATION_WINDOW_HEADLINE} trading days "
            f"({returns.index[-config.CORRELATION_WINDOW_HEADLINE].date()} to {returns.index[-1].date()})",
        ),
    ]

    for ax, corr_matrix, subtitle in panels:
        image = ax.imshow(corr_matrix.values, vmin=-1, vmax=1, cmap=DIVERGING_COLORMAP)
        ax.set_xticks(range(len(labels)))
        ax.set_xticklabels(labels, rotation=45, ha="right")
        ax.set_yticks(range(len(labels)))
        ax.set_yticklabels(labels)
        ax.set_title(subtitle, fontsize=9)

        for row in range(len(labels)):
            for col in range(len(labels)):
                value = corr_matrix.values[row, col]
                text_color = TEXT_PRIMARY if abs(value) < 0.6 else "white"
                ax.text(col, row, f"{value:.2f}", ha="center", va="center", fontsize=7, color=text_color)

    fig.suptitle("Correlation of daily log returns across assets (Pearson)")
    fig.colorbar(image, ax=axes, shrink=0.8, label="Pearson correlation (unitless, -1 to 1)")

    add_caption(
        fig,
        "Source: yfinance, daily log returns aligned to the Nasdaq trading calendar (BUILD-SPEC section 6.1). "
        "Numeric value printed in every cell so the chart reads without color.",
    )

    return save_figure(fig, filename)


def main():
    """
    Generate figures 1, 2, and 4 from the already-built database and panel.

    Why it exists: this is the entry point src/run_all.py calls after
    Phase 4's correlations are loaded into btc_regime.db (BUILD-SPEC
    section 12's Phase 4 acceptance criterion: "figures 1, 2 and 4
    render").

    Parameters:
        None.

    Returns:
        None.
    """
    panel = pd.read_parquet(config.PANEL_PATH)
    conn = sqlite3.connect(config.DB_PATH)
    try:
        pairs = list(config.CORRELATION_PAIRS)

        correlations_90d_pearson = load_rolling_correlations_wide(conn, config.CORRELATION_WINDOW_HEADLINE, "pearson", pairs)
        plot_rolling_correlations_overview(correlations_90d_pearson)

        correlations_30d_pearson = load_rolling_correlations_wide(conn, config.CORRELATION_WINDOW_SHORT, "pearson", pairs)
        sensitivity_pair = config.WINDOW_SENSITIVITY_PAIR
        plot_window_sensitivity(
            correlations_30d_pearson[sensitivity_pair].dropna(),
            correlations_90d_pearson[sensitivity_pair].dropna(),
            sensitivity_pair,
        )

        log_return_columns = [f"log_return_{ticker}" for ticker in config.MARKET_TICKERS]
        column_labels = {f"log_return_{ticker}": ticker for ticker in config.MARKET_TICKERS}
        plot_correlation_heatmap(panel, log_return_columns, column_labels)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
    sys.exit(0)
