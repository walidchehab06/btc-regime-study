"""
Every figure the project produces, one function per figure, per
BUILD-SPEC-bitcoin-regime-study.md section 9 and section 12 (Phase 4 for
figures 1, 2, and 4; later phases add the rest).

Why this file exists: section 9 requires matplotlib only (no seaborn, no
plotly), one consistent palette defined once, and every figure legible in
greyscale -- this module is that one place the palette and shared chart
conventions live, so every figure looks like it came from the same study.
"""

import itertools
import sys

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import pandas as pd
import sqlite3
from matplotlib.colors import LinearSegmentedColormap
from matplotlib.patches import Patch

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

# --- Regime palette (BUILD-SPEC section 9, Phase 5) ---
# Slots 4-7 of the same eight-hue colorblind-validated sequence PAIR_COLORS
# draws its first three slots (1-3, blue/orange/aqua) from -- distinct
# colors so figure 1 can show regime bands and pair lines together without
# confusion. Validated all-pairs, not just adjacent-in-list, since any two
# regimes can sit next to each other in the timeline: worst-case CVD delta
# 16.2, worst-case normal-vision delta 19.6, both clear of the validator's
# floors. Two of the four (yellow, magenta) fall below 3:1 contrast on a
# white surface, which is why every band also carries a direct text label
# in figure 3 and the before/after chart, not color alone.
REGIME_COLORS = {
    "IDIOSYNCRATIC": "#eda100",  # yellow
    "MIXED": "#e87ba4",  # magenta
    "RISK_ASSET": "#008300",  # green
    "HARD_ASSET": "#4a3aa7",  # violet
}
REGIME_DISPLAY_LABELS = {
    "RISK_ASSET": "Risk asset",
    "HARD_ASSET": "Hard asset",
    "IDIOSYNCRATIC": "Idiosyncratic",
    "MIXED": "Mixed",
}
REGIME_LEGEND_ORDER = ["RISK_ASSET", "HARD_ASSET", "IDIOSYNCRATIC", "MIXED"]

# Sequential single-hue ramp (light -> dark blue) for figure 5's heatmap,
# a magnitude encoding (number of regime periods), per the project's
# "no rainbow colormap" rule (section 9). Endpoints from the same
# palette's blue sequential ramp.
SEQUENTIAL_BLUE_CMAP = LinearSegmentedColormap.from_list("sequential_blue", ["#cde2fb", "#0d366b"])

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
        for _, period in regime_periods.iterrows():
            start = pd.Timestamp(period["start_date"])
            end = pd.Timestamp(period["end_date"])
            color = REGIME_COLORS.get(period["regime_label"], BASELINE)
            ax.axvspan(start, end, color=color, alpha=0.15, linewidth=0, zorder=-1)

    ax.set_ylim(-1.0, 1.0)
    ax.set_xlabel("Date")
    ax.set_ylabel("90-day Pearson correlation of daily log returns (unitless, -1 to 1)")
    ax.set_title("Bitcoin's rolling 90-day correlation with Nasdaq, gold, and the dollar index")
    ax.grid(True, color=GRIDLINE, linewidth=0.5)
    lines_legend = ax.legend(loc="upper left", frameon=False)

    if regime_periods is not None and len(regime_periods) > 0:
        ax.add_artist(lines_legend)
        regime_handles = [
            Patch(facecolor=REGIME_COLORS[label], alpha=0.3, label=REGIME_DISPLAY_LABELS[label])
            for label in REGIME_LEGEND_ORDER
            if label in regime_periods["regime_label"].unique()
        ]
        ax.legend(handles=regime_handles, loc="lower left", frameon=False, fontsize=8, title="Regime (shaded)")

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


def plot_regime_timeline(regime_periods, btc_price, filename="fig03_regime_timeline.png"):
    """
    Figure 3: Bitcoin's price on a log scale, with a colored horizontal
    band across the study period showing which regime each day fell into.

    Why it exists: BUILD-SPEC section 9, figure 3 -- the direct visual
    answer to "when was Bitcoin behaving like a risk asset, a hard asset,
    both, or neither."

    Parameters:
        regime_periods: pandas.DataFrame with columns start_date,
            end_date, regime_label, from src/regimes.py's
            build_regime_periods() or the regime_periods SQLite table.
        btc_price: pandas.Series indexed by date (datetime), Bitcoin's
            close price, e.g. panel["close_BTC-USD"].
        filename: str, output filename under outputs/figures/.

    Returns:
        pathlib.Path, the saved figure's path.
    """
    fig, (price_ax, band_ax) = plt.subplots(
        2, 1, figsize=(11, 6), sharex=True, gridspec_kw={"height_ratios": [4, 1], "hspace": 0.06}
    )

    price_ax.plot(btc_price.index, btc_price.values, color=TEXT_PRIMARY, linewidth=1.2)
    price_ax.set_yscale("log")
    price_ax.set_ylabel("BTC-USD close (log scale, USD)")
    price_ax.set_title("Bitcoin's cross-asset regime over time")
    price_ax.grid(True, which="both", color=GRIDLINE, linewidth=0.4)

    for _, period in regime_periods.iterrows():
        start = pd.Timestamp(period["start_date"])
        end = pd.Timestamp(period["end_date"])
        color = REGIME_COLORS.get(period["regime_label"], BASELINE)
        band_ax.axvspan(start, end, color=color, linewidth=0)

    band_ax.set_yticks([])
    band_ax.set_ylim(0, 1)
    band_ax.set_xlabel("Date")

    # Direct text labels, one per band, kept only where they actually fit.
    # "Fit" is checked against the label's real rendered pixel width (via
    # the figure's own renderer), not guessed from its character count --
    # a label that looks like it should fit a narrow band can still spill
    # into a neighboring band once matplotlib actually lays it out. A
    # label survives only if its own box sits inside its band's edges AND
    # doesn't overlap the previous surviving label's right edge.
    fig.canvas.draw()
    renderer = fig.canvas.get_renderer()
    previous_label_right_pixels = None
    for _, period in regime_periods.iterrows():
        start = pd.Timestamp(period["start_date"])
        end = pd.Timestamp(period["end_date"])
        display_label = REGIME_DISPLAY_LABELS.get(period["regime_label"], period["regime_label"])
        midpoint = start + (end - start) / 2

        text_obj = band_ax.text(midpoint, 0.5, display_label, ha="center", va="center", fontsize=7, color="white")
        text_box_pixels = text_obj.get_window_extent(renderer=renderer)
        band_left_pixels = band_ax.transData.transform((mdates.date2num(start), 0.5))[0]
        band_right_pixels = band_ax.transData.transform((mdates.date2num(end), 0.5))[0]

        fits_its_own_band = text_box_pixels.x0 >= band_left_pixels and text_box_pixels.x1 <= band_right_pixels
        clears_previous_label = previous_label_right_pixels is None or text_box_pixels.x0 >= previous_label_right_pixels

        if fits_its_own_band and clears_previous_label:
            previous_label_right_pixels = text_box_pixels.x1
        else:
            text_obj.remove()

    handles = [Patch(facecolor=REGIME_COLORS[label], label=REGIME_DISPLAY_LABELS[label]) for label in REGIME_LEGEND_ORDER]
    band_ax.legend(handles=handles, loc="upper center", bbox_to_anchor=(0.5, -0.45), ncol=4, frameon=False, fontsize=8)

    date_range = f"{btc_price.index.min().date()} to {btc_price.index.max().date()}"
    add_caption(
        fig,
        f"Source: yfinance (BTC-USD close). Regime labels from 90-day Pearson correlations "
        f"with Nasdaq and gold, {config.REGIME_PERSISTENCE_MIN_DAYS}-trading-day persistence "
        f"filter applied, {date_range}. Some narrow bands are unlabeled to avoid crowding; "
        "see outputs/tables/query_09_regime_timeline.csv for every period's exact dates.",
    )

    return save_figure(fig, filename)


def plot_sensitivity_heatmap(sensitivity_grid, filename="fig05_sensitivity_heatmap.png"):
    """
    Figure 5: the BUILD-SPEC section 6.5 sensitivity grid -- the number of
    regime periods identified at every combination of Nasdaq and gold
    correlation thresholds, each cell marked for whether the regime shift
    identified during 2026 at baseline thresholds survives that
    combination.

    Why it exists: BUILD-SPEC section 9, figure 5. Answers "why those
    threshold numbers" by showing how much the result actually depends on
    them, per section 6.5's mandatory sensitivity analysis.

    Parameters:
        sensitivity_grid: pandas.DataFrame from
            src/regimes.py:run_sensitivity_grid(), columns
            nasdaq_threshold, gold_threshold, n_regime_periods,
            shift_survives_2026.
        filename: str, output filename under outputs/figures/.

    Returns:
        pathlib.Path, the saved figure's path.
    """
    nasdaq_thresholds = sorted(sensitivity_grid["nasdaq_threshold"].unique())
    gold_thresholds = sorted(sensitivity_grid["gold_threshold"].unique())

    n_periods_wide = sensitivity_grid.pivot(
        index="gold_threshold", columns="nasdaq_threshold", values="n_regime_periods"
    ).loc[gold_thresholds, nasdaq_thresholds]
    survives_wide = sensitivity_grid.pivot(
        index="gold_threshold", columns="nasdaq_threshold", values="shift_survives_2026"
    ).loc[gold_thresholds, nasdaq_thresholds]

    fig, ax = plt.subplots(figsize=(7.5, 6))
    image = ax.imshow(n_periods_wide.values, cmap=SEQUENTIAL_BLUE_CMAP)

    ax.set_xticks(range(len(nasdaq_thresholds)))
    ax.set_xticklabels([f"{t:.2f}" for t in nasdaq_thresholds])
    ax.set_yticks(range(len(gold_thresholds)))
    ax.set_yticklabels([f"{t:.2f}" for t in gold_thresholds])
    ax.set_xlabel("Nasdaq correlation threshold")
    ax.set_ylabel("Gold correlation threshold")
    ax.set_title("Sensitivity grid: regime periods identified and whether the 2026 shift survives")

    color_midpoint = n_periods_wide.values.max() * 0.6
    for row in range(len(gold_thresholds)):
        for col in range(len(nasdaq_thresholds)):
            n_periods = int(n_periods_wide.values[row, col])
            survives = bool(survives_wide.values[row, col])
            mark = "✓" if survives else "✗"
            text_color = "white" if n_periods >= color_midpoint else TEXT_PRIMARY
            ax.text(col, row, f"{n_periods}\n{mark}", ha="center", va="center", fontsize=8, color=text_color)

    fig.colorbar(image, ax=ax, label="Number of regime periods")

    add_caption(
        fig,
        f"Source: rolling_correlations (90-day Pearson BTC_NASDAQ, BTC_GOLD). "
        f"{config.REGIME_PERSISTENCE_MIN_DAYS}-day persistence filter applied at every "
        "threshold combination. Checkmark: a regime transition falls in calendar year 2026 "
        "at that combination; cross: it does not. See outputs/tables/sensitivity_grid.csv.",
    )

    return save_figure(fig, filename)


def plot_regime_label_stability_before_after(
    dates, raw_labels, filtered_labels, filename="regime_label_stability_before_after.png"
):
    """
    Before/after diagnostic: raw daily regime labels (no persistence
    filter) against the filtered labels, same time axis, showing the
    filter turning day-to-day flicker into stable multi-week periods.

    Why it exists: BUILD-SPEC section 6.4 requires documenting the
    persistence filter with exactly this comparison. Not one of the 10
    numbered figures in section 9 -- a supporting diagnostic referenced
    from docs/methodology.md.

    Parameters:
        dates: pandas.DatetimeIndex, chronological.
        raw_labels: list of str, one per date, unfiltered
            (src/regimes.py:classify_regime_series()).
        filtered_labels: list of str, one per date, same length, filtered
            (src/regimes.py:apply_persistence_filter()).
        filename: str, output filename under outputs/figures/.

    Returns:
        pathlib.Path, the saved figure's path.
    """

    def label_spans(labels):
        spans = []
        position = 0
        for label, group in itertools.groupby(labels):
            length = len(list(group))
            spans.append((label, dates[position], dates[position + length - 1]))
            position += length
        return spans

    fig, (raw_ax, filtered_ax) = plt.subplots(2, 1, figsize=(11, 3), sharex=True, gridspec_kw={"hspace": 0.35})

    for ax, labels, title in (
        (raw_ax, raw_labels, "Raw (no persistence filter)"),
        (filtered_ax, filtered_labels, f"Filtered ({config.REGIME_PERSISTENCE_MIN_DAYS}-day persistence filter)"),
    ):
        for label, start, end in label_spans(labels):
            ax.axvspan(start, end, color=REGIME_COLORS.get(label, BASELINE), linewidth=0)
        ax.set_yticks([])
        ax.set_ylim(0, 1)
        ax.set_title(title, fontsize=9, loc="left")

    handles = [Patch(facecolor=REGIME_COLORS[label], label=REGIME_DISPLAY_LABELS[label]) for label in REGIME_LEGEND_ORDER]
    filtered_ax.legend(handles=handles, loc="upper center", bbox_to_anchor=(0.5, -0.6), ncol=4, frameon=False, fontsize=8)

    add_caption(
        fig,
        "Source: rolling_correlations, 90-day Pearson BTC_NASDAQ/BTC_GOLD, same underlying "
        "days in both strips. Raw labels change with every threshold crossing; filtered "
        "labels only change when a run holds for at least "
        f"{config.REGIME_PERSISTENCE_MIN_DAYS} trading days.",
    )

    return save_figure(fig, filename)


def main():
    """
    Generate figures 1, 2, 3, 4, and 5 from the already-built database and
    panel.

    Why it exists: this is the entry point src/run_all.py calls once,
    after both Phase 4 (correlations) and Phase 5 (regimes) have loaded
    their tables into btc_regime.db -- figure 1 needs regime_periods for
    its shaded bands, and figures 3 and 5 need regime_periods and
    outputs/tables/sensitivity_grid.csv directly, so this can no longer
    run right after Phase 4 alone. See docs/decisions-log.md.

    Parameters:
        None.

    Returns:
        None.
    """
    panel = pd.read_parquet(config.PANEL_PATH)
    conn = sqlite3.connect(config.DB_PATH)
    try:
        pairs = list(config.CORRELATION_PAIRS)
        regime_periods = pd.read_sql_query("SELECT * FROM regime_periods ORDER BY start_date", conn)

        correlations_90d_pearson = load_rolling_correlations_wide(conn, config.CORRELATION_WINDOW_HEADLINE, "pearson", pairs)
        plot_rolling_correlations_overview(correlations_90d_pearson, regime_periods=regime_periods)

        correlations_30d_pearson = load_rolling_correlations_wide(conn, config.CORRELATION_WINDOW_SHORT, "pearson", pairs)
        sensitivity_pair = config.WINDOW_SENSITIVITY_PAIR
        plot_window_sensitivity(
            correlations_30d_pearson[sensitivity_pair].dropna(),
            correlations_90d_pearson[sensitivity_pair].dropna(),
            sensitivity_pair,
        )

        plot_regime_timeline(regime_periods, panel["close_BTC-USD"])

        log_return_columns = [f"log_return_{ticker}" for ticker in config.MARKET_TICKERS]
        column_labels = {f"log_return_{ticker}": ticker for ticker in config.MARKET_TICKERS}
        plot_correlation_heatmap(panel, log_return_columns, column_labels)

        sensitivity_grid = pd.read_csv(config.SENSITIVITY_GRID_TABLE_PATH)
        plot_sensitivity_heatmap(sensitivity_grid)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
    sys.exit(0)
