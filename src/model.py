"""
The machine-learning component: multinomial logistic regression and a
shallow decision tree predicting the regime label 5 trading days ahead,
walk-forward validated against a persistence baseline and a majority-
class baseline, per BUILD-SPEC-bitcoin-regime-study.md section 12
(Phase 8).

Why this file exists: section 6.7 requires this to be deliberately small,
interpretable, and honestly evaluated -- every feature computable from
information available on the prediction date only, validation that never
shuffles time, and both naive baselines reported alongside the models
even when (especially when) they win. See docs/ml-caveats.md and
docs/decisions-log.md for the reasoning behind the specific choices made
here.
"""

import sys

import numpy as np
import pandas as pd
import sqlite3
from sklearn.compose import ColumnTransformer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, balanced_accuracy_score, confusion_matrix, f1_score
from sklearn.model_selection import TimeSeriesSplit
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.tree import DecisionTreeClassifier

from src import charts, config

# The continuous features, in a fixed order -- StandardScaler is applied
# to exactly these columns (build_logistic_regression_pipeline()); the
# one-hot current-regime columns are deliberately left out, since scaling
# a 0/1 indicator doesn't mean anything.
CONTINUOUS_FEATURE_COLUMNS = [
    "corr_30_BTC_NASDAQ",
    "corr_30_BTC_GOLD",
    "corr_30_BTC_DXY",
    "corr_90_BTC_NASDAQ",
    "corr_90_BTC_GOLD",
    "corr_90_BTC_DXY",
    "realized_vol_20",
    "btc_momentum_20",
    "dxy_change_20",
    "real_yield_change_20",
    "fng_level",
    "fng_change_14",
]

ONE_HOT_REGIME_COLUMNS = [f"regime_{label}" for label in config.ML_REGIME_LABEL_ORDER]

METHOD_ORDER = ["persistence", "majority_class", "logistic_regression", "decision_tree"]


def load_panel():
    """
    Load the primary daily panel built in Phase 2.

    Why it exists: same pattern as every other phase module -- one place
    reads panel_daily.parquet, per CLAUDE.md's row-count-on-load logging.

    Parameters:
        None.

    Returns:
        pandas.DataFrame indexed by date (datetime), as saved by
        src/build_panel.py.
    """
    panel = pd.read_parquet(config.PANEL_PATH)
    print(f"[model] loaded {config.PANEL_PATH}: {len(panel)} rows, {len(panel.columns)} columns")
    return panel


def load_correlation_features(conn):
    """
    Load the 30-day and 90-day Pearson correlations for BTC_NASDAQ,
    BTC_GOLD, and BTC_DXY into one wide DataFrame, one column per
    window/pair combination.

    Why it exists: section 6.7's feature list asks for "current 30-day and
    90-day correlations with Nasdaq, gold, DXY" -- these are already
    computed and stored by Phase 4 in rolling_correlations; this just
    reshapes that long table into the wide feature columns
    build_feature_matrix() merges in.

    Parameters:
        conn: sqlite3.Connection, open connection to btc_regime.db.

    Returns:
        pandas.DataFrame indexed by date (datetime), columns named
        "corr_<window>_<pair>", e.g. "corr_90_BTC_NASDAQ".
    """
    pairs = list(config.CORRELATION_PAIRS)
    windows = [config.CORRELATION_WINDOW_SHORT, config.CORRELATION_WINDOW_HEADLINE]
    pair_placeholders = ",".join("?" for _ in pairs)
    window_placeholders = ",".join("?" for _ in windows)
    query = (
        "SELECT date, pair, window, correlation FROM rolling_correlations "
        f"WHERE method = ? AND pair IN ({pair_placeholders}) AND window IN ({window_placeholders})"
    )
    long_df = pd.read_sql_query(query, conn, params=[config.ML_CORRELATION_METHOD, *pairs, *windows])
    long_df["date"] = pd.to_datetime(long_df["date"])
    long_df["column"] = "corr_" + long_df["window"].astype(str) + "_" + long_df["pair"]
    wide_df = long_df.pivot(index="date", columns="column", values="correlation").sort_index()
    print(f"[model] loaded {len(long_df)} rolling_correlations rows -> wide {wide_df.shape}")
    return wide_df


def load_regime_labels(conn):
    """
    Load the day-by-day regime label series Phase 5 loaded into SQLite.

    Why it exists: this single series is used twice here -- shifted
    forward to build the prediction target (build_target()), and as-is
    (the "current regime label") both as a feature and as the persistence
    baseline's prediction.

    Parameters:
        conn: sqlite3.Connection, open connection to btc_regime.db.

    Returns:
        pandas.Series of str, indexed by date (datetime), from the
        regimes table.
    """
    long_df = pd.read_sql_query("SELECT date, regime_label FROM regimes ORDER BY date", conn)
    long_df["date"] = pd.to_datetime(long_df["date"])
    series = long_df.set_index("date")["regime_label"]
    print(f"[model] loaded {len(series)} regimes rows")
    return series


def compute_technical_features(panel):
    """
    Compute the non-correlation features from section 6.7's list: 20-day
    realized BTC volatility, 20-day BTC momentum, 20-day DXY change,
    20-day real-yield change, the Fear & Greed level, and its 14-day
    change.

    Why it exists: these six features aren't already stored anywhere --
    each is a trailing rolling calculation over panel_daily.parquet
    columns, computed here rather than centered or forward-looking, per
    section 6.7's no-look-ahead requirement.

    Parameters:
        panel: pandas.DataFrame, the primary daily panel, indexed by
            date, from load_panel().

    Returns:
        pandas.DataFrame indexed like panel, columns realized_vol_20,
        btc_momentum_20, dxy_change_20, real_yield_change_20, fng_level,
        fng_change_14. NaN for any date inside a feature's warm-up window.
    """
    btc_log_return = panel["log_return_BTC-USD"]
    features = pd.DataFrame(index=panel.index)

    # Population std (ddof=0), matching core_math.annualized_volatility's
    # convention, so this feature and the section 6.4 per-regime
    # volatility figure agree on what "volatility" means.
    features["realized_vol_20"] = btc_log_return.rolling(config.ML_VOLATILITY_WINDOW_DAYS).std(
        ddof=0
    ) * np.sqrt(config.TRADING_DAYS_PER_YEAR)

    features["btc_momentum_20"] = btc_log_return.rolling(config.ML_MOMENTUM_WINDOW_DAYS).sum()
    features["dxy_change_20"] = panel[config.ML_DXY_FEATURE_COLUMN].diff(config.ML_DXY_CHANGE_WINDOW_DAYS)
    features["real_yield_change_20"] = panel[config.ML_REAL_YIELD_COLUMN].diff(
        config.ML_REAL_YIELD_CHANGE_WINDOW_DAYS
    )
    features["fng_level"] = panel["fng_value"]
    features["fng_change_14"] = panel["fng_value"].diff(config.ML_SENTIMENT_CHANGE_WINDOW_DAYS)

    print(f"[model] computed {len(features.columns)} technical features for {len(features)} dates")
    return features


def build_feature_matrix(panel, correlation_features, regime_labels):
    """
    Merge the technical features, the correlation features, and a one-hot
    encoding of the current regime label into one feature matrix, and
    drop the warm-up rows any feature is still NaN for.

    Why it exists: section 6.7's full feature list, assembled in one
    place. Keeps the plain (non-one-hot) current regime label alongside
    the matrix too, since the persistence baseline needs it directly
    rather than having to decode it back out of one-hot columns.

    Parameters:
        panel: pandas.DataFrame, the primary daily panel, indexed by
            date, from load_panel().
        correlation_features: pandas.DataFrame indexed by date, from
            load_correlation_features().
        regime_labels: pandas.Series indexed by date, from
            load_regime_labels().

    Returns:
        (X, current_regime_label) tuple:
        X: pandas.DataFrame indexed by date, columns
            CONTINUOUS_FEATURE_COLUMNS + ONE_HOT_REGIME_COLUMNS, no NaNs.
        current_regime_label: pandas.Series of str, same index as X.
    """
    technical_features = compute_technical_features(panel)
    print(f"[model] technical features: {len(technical_features)} rows before merge")

    merged = technical_features.join(correlation_features, how="inner")
    print(f"[model] after joining correlation features: {len(merged)} rows")

    merged = merged.join(regime_labels.rename("current_regime_label"), how="inner")
    print(f"[model] after joining current regime label: {len(merged)} rows")

    one_hot = pd.get_dummies(merged["current_regime_label"], prefix="regime")
    for column in ONE_HOT_REGIME_COLUMNS:
        if column not in one_hot.columns:
            one_hot[column] = 0
    one_hot = one_hot[ONE_HOT_REGIME_COLUMNS].astype(int)

    X = pd.concat([merged[CONTINUOUS_FEATURE_COLUMNS], one_hot], axis=1)
    current_regime_label = merged["current_regime_label"]

    n_before_dropna = len(X)
    valid_mask = X.notna().all(axis=1)
    X = X[valid_mask]
    current_regime_label = current_regime_label[valid_mask]
    print(
        f"[model] dropped {n_before_dropna - len(X)} warm-up rows with at least one NaN "
        f"feature -> {len(X)} usable rows"
    )
    return X, current_regime_label


def build_target(regime_labels, horizon_days):
    """
    Build the prediction target: the regime label horizon_days trading
    days after each date.

    Why it exists: section 6.7's task definition, exactly. The trailing
    horizon_days dates (nearest the end of the series) have no future
    label to look up and get NaN, which assemble_dataset() then drops.

    Parameters:
        regime_labels: pandas.Series of str, indexed by date, from
            load_regime_labels().
        horizon_days: int, e.g. config.ML_TARGET_HORIZON_DAYS.

    Returns:
        pandas.Series of str, same index as regime_labels, each value the
        regime label horizon_days trading days later (NaN for the
        trailing horizon_days dates).
    """
    target = regime_labels.shift(-horizon_days)
    n_missing = int(target.isna().sum())
    print(
        f"[model] target = regime label {horizon_days} trading days ahead; "
        f"{n_missing} trailing rows have no target"
    )
    return target


def assemble_dataset(conn, panel):
    """
    Build the full feature matrix, target, and current-regime-label
    series, aligned to the same dates, and write the combined table to
    outputs/tables/ml_features_daily.csv.

    Why it exists: the single entry point main() calls to go from the
    already-built database and panel to a model-ready (X, y,
    current_regime_label) triple -- every number that follows in this
    module traces back to the CSV this writes.

    Parameters:
        conn: sqlite3.Connection, open connection to btc_regime.db.
        panel: pandas.DataFrame, the primary daily panel, from
            load_panel().

    Returns:
        (X, y, current_regime_label) tuple, all pandas objects sharing
        the same DatetimeIndex, no NaNs anywhere.
    """
    correlation_features = load_correlation_features(conn)
    regime_labels = load_regime_labels(conn)
    X, current_regime_label = build_feature_matrix(panel, correlation_features, regime_labels)

    target = build_target(regime_labels, config.ML_TARGET_HORIZON_DAYS).reindex(X.index)
    has_target = target.notna()
    n_dropped = int((~has_target).sum())
    print(
        f"[model] dropping {n_dropped} rows with no {config.ML_TARGET_HORIZON_DAYS}-trading-day-ahead "
        f"target (the end of the series) -> {int(has_target.sum())} rows in the final dataset"
    )

    X = X[has_target]
    y = target[has_target]
    current_regime_label = current_regime_label[has_target]

    features_table = X.copy()
    features_table["current_regime_label"] = current_regime_label
    features_table["target_regime_label"] = y
    config.OUTPUTS_TABLES_DIR.mkdir(parents=True, exist_ok=True)
    features_table.to_csv(config.ML_FEATURES_TABLE_PATH)
    print(f"[model] wrote {len(features_table)} rows -> {config.ML_FEATURES_TABLE_PATH}")

    return X, y, current_regime_label


def build_logistic_regression_pipeline():
    """
    Build the multinomial logistic regression pipeline: scale the
    continuous features, pass the one-hot regime columns through
    unscaled, then classify.

    Why it exists: section 6.7 asks for multinomial logistic regression
    specifically; scikit-learn's LogisticRegression fits a multinomial
    model automatically once the target has more than two classes.

    Parameters:
        None.

    Returns:
        sklearn.pipeline.Pipeline, unfit.
    """
    preprocessor = ColumnTransformer(
        [("scale", StandardScaler(), CONTINUOUS_FEATURE_COLUMNS)],
        remainder="passthrough",
    )
    return Pipeline(
        [
            ("preprocess", preprocessor),
            (
                "classify",
                LogisticRegression(max_iter=config.ML_LOGISTIC_MAX_ITER, random_state=config.ML_RANDOM_STATE),
            ),
        ]
    )


def build_decision_tree_model():
    """
    Build the decision tree classifier, depth-capped per section 6.7.

    Why it exists: one line, but every model-construction call in this
    module goes through a function so the two places a tree gets built
    (inside the walk-forward loop, and the full-history illustrative fit
    for figure 9) can never drift apart in configuration.

    Parameters:
        None.

    Returns:
        sklearn.tree.DecisionTreeClassifier, unfit.
    """
    return DecisionTreeClassifier(max_depth=config.ML_TREE_MAX_DEPTH, random_state=config.ML_RANDOM_STATE)


def compute_metrics(y_true, y_pred, labels):
    """
    Compute accuracy, balanced accuracy, and macro F1 for one set of
    predictions.

    Why it exists: section 6.7 requires all three metrics reported for
    every baseline and every model, computed the same way each time.

    Parameters:
        y_true: array-like of str, true regime labels.
        y_pred: array-like of str, predicted regime labels.
        labels: list of str, the fixed class order (config.ML_REGIME_LABEL_ORDER).

    Returns:
        dict with keys accuracy, balanced_accuracy, macro_f1 (floats).
    """
    return {
        "accuracy": float(accuracy_score(y_true, y_pred)),
        "balanced_accuracy": float(balanced_accuracy_score(y_true, y_pred)),
        "macro_f1": float(f1_score(y_true, y_pred, labels=labels, average="macro", zero_division=0)),
    }


def run_walk_forward_evaluation(X, y, current_regime_label):
    """
    Run the persistence baseline, the majority-class baseline, logistic
    regression, and the decision tree through the same
    TimeSeriesSplit walk-forward loop, collecting every fold's
    out-of-fold predictions and per-fold metrics.

    Why it exists: section 6.7's validation requirement, applied
    identically to baselines and models so the comparison is apples to
    apples -- the majority-class baseline is recomputed from each fold's
    own training labels (never a single global mode), and the
    persistence baseline is just that fold's current_regime_label on the
    test dates, no fitting involved.

    Parameters:
        X: pandas.DataFrame, feature matrix from assemble_dataset().
        y: pandas.Series of str, target from assemble_dataset().
        current_regime_label: pandas.Series of str, same index as X, from
            assemble_dataset().

    Returns:
        (oof_predictions_df, fold_metrics_df) tuple:
        oof_predictions_df: pandas.DataFrame, one row per
            (fold, date, method), columns fold, date, method, y_true,
            y_pred.
        fold_metrics_df: pandas.DataFrame, one row per (fold, method),
            columns fold, method, n_test, accuracy, balanced_accuracy,
            macro_f1. Also written to config.ML_PER_FOLD_METRICS_TABLE_PATH.
    """
    splitter = TimeSeriesSplit(n_splits=config.ML_TIMESERIES_N_SPLITS, gap=config.ML_TIMESERIES_GAP_DAYS)

    oof_rows = []
    fold_metric_rows = []

    for fold_number, (train_idx, test_idx) in enumerate(splitter.split(X), start=1):
        X_train, X_test = X.iloc[train_idx], X.iloc[test_idx]
        y_train, y_test = y.iloc[train_idx], y.iloc[test_idx]
        test_dates = X.index[test_idx]
        print(
            f"[model] fold {fold_number}: train {len(train_idx)} rows "
            f"({X.index[train_idx[0]].date()} to {X.index[train_idx[-1]].date()}), "
            f"test {len(test_idx)} rows ({test_dates[0].date()} to {test_dates[-1].date()})"
        )

        predictions = {}

        predictions["persistence"] = current_regime_label.iloc[test_idx].to_numpy()

        majority_label = y_train.mode().iloc[0]
        predictions["majority_class"] = np.full(len(test_idx), majority_label, dtype=object)

        logistic_pipeline = build_logistic_regression_pipeline()
        logistic_pipeline.fit(X_train, y_train)
        predictions["logistic_regression"] = logistic_pipeline.predict(X_test)

        tree_model = build_decision_tree_model()
        tree_model.fit(X_train, y_train)
        predictions["decision_tree"] = tree_model.predict(X_test)

        for method in METHOD_ORDER:
            y_pred = predictions[method]
            metrics = compute_metrics(y_test.to_numpy(), y_pred, config.ML_REGIME_LABEL_ORDER)
            fold_metric_rows.append({"fold": fold_number, "method": method, "n_test": len(test_idx), **metrics})
            for date, y_true_value, y_pred_value in zip(test_dates, y_test.to_numpy(), y_pred):
                oof_rows.append(
                    {
                        "fold": fold_number,
                        "date": date.strftime("%Y-%m-%d"),
                        "method": method,
                        "y_true": y_true_value,
                        "y_pred": y_pred_value,
                    }
                )

    oof_predictions_df = pd.DataFrame(oof_rows)
    fold_metrics_df = pd.DataFrame(fold_metric_rows)

    config.OUTPUTS_TABLES_DIR.mkdir(parents=True, exist_ok=True)
    fold_metrics_df.to_csv(config.ML_PER_FOLD_METRICS_TABLE_PATH, index=False)
    print(f"[model] wrote per-fold metrics -> {config.ML_PER_FOLD_METRICS_TABLE_PATH}")

    return oof_predictions_df, fold_metrics_df


def build_model_comparison_table(oof_predictions_df, labels):
    """
    Aggregate every method's concatenated out-of-fold predictions
    (across all walk-forward folds) into one comparison table, and print
    the plain-language headline comparison section 6.7's honesty
    requirement calls for.

    Why it exists: reporting metrics per fold (fold_metrics_df) shows
    stability over time; this table is the single honest summary number
    per method -- computed on every out-of-fold prediction pooled
    together, not averaged across folds of different sizes.

    Parameters:
        oof_predictions_df: pandas.DataFrame from
            run_walk_forward_evaluation().
        labels: list of str, the fixed class order (config.ML_REGIME_LABEL_ORDER).

    Returns:
        pandas.DataFrame, one row per method in METHOD_ORDER, columns
        method, n_test_total, accuracy, balanced_accuracy, macro_f1. Also
        written to config.ML_MODEL_COMPARISON_TABLE_PATH.
    """
    rows = []
    for method in METHOD_ORDER:
        group = oof_predictions_df[oof_predictions_df["method"] == method]
        metrics = compute_metrics(group["y_true"].to_numpy(), group["y_pred"].to_numpy(), labels)
        rows.append({"method": method, "n_test_total": len(group), **metrics})

    comparison_df = pd.DataFrame(rows)
    config.OUTPUTS_TABLES_DIR.mkdir(parents=True, exist_ok=True)
    comparison_df.to_csv(config.ML_MODEL_COMPARISON_TABLE_PATH, index=False)

    persistence_accuracy = comparison_df.loc[comparison_df["method"] == "persistence", "accuracy"].iloc[0]
    print(f"[model] === headline comparison (pooled out-of-fold predictions, all folds) ===")
    for _, row in comparison_df.iterrows():
        note = ""
        if row["method"] not in ("persistence", "majority_class"):
            note = " -- BEATS persistence baseline" if row["accuracy"] > persistence_accuracy else " -- does NOT beat persistence baseline"
        print(
            f"[model]   {row['method']}: accuracy={row['accuracy']:.3f} "
            f"balanced_accuracy={row['balanced_accuracy']:.3f} macro_f1={row['macro_f1']:.3f}{note}"
        )
    print(f"[model] wrote model comparison -> {config.ML_MODEL_COMPARISON_TABLE_PATH}")

    return comparison_df


def build_confusion_matrices(oof_predictions_df, labels):
    """
    Compute each method's confusion matrix over its pooled out-of-fold
    predictions, and write a long-format table with every cell.

    Why it exists: section 6.7 requires a confusion matrix per method;
    the long format (one row per method/true_label/pred_label) is what
    outputs/tables/ files should look like per section 8's "every number
    quoted in the write-up has a file behind it," and charts.py pivots it
    back into a grid for figure 8.

    Parameters:
        oof_predictions_df: pandas.DataFrame from
            run_walk_forward_evaluation().
        labels: list of str, the fixed class order (config.ML_REGIME_LABEL_ORDER).

    Returns:
        dict mapping method -> numpy.ndarray (len(labels) x len(labels)
        confusion matrix, rows = true label, columns = predicted label,
        same order as labels). Also written long-format to
        config.ML_CONFUSION_MATRICES_TABLE_PATH.
    """
    matrices = {}
    rows = []
    for method in METHOD_ORDER:
        group = oof_predictions_df[oof_predictions_df["method"] == method]
        matrix = confusion_matrix(group["y_true"], group["y_pred"], labels=labels)
        matrices[method] = matrix
        for i, true_label in enumerate(labels):
            for j, pred_label in enumerate(labels):
                rows.append(
                    {"method": method, "true_label": true_label, "pred_label": pred_label, "count": int(matrix[i, j])}
                )

    long_df = pd.DataFrame(rows)
    config.OUTPUTS_TABLES_DIR.mkdir(parents=True, exist_ok=True)
    long_df.to_csv(config.ML_CONFUSION_MATRICES_TABLE_PATH, index=False)
    print(f"[model] wrote confusion matrices -> {config.ML_CONFUSION_MATRICES_TABLE_PATH}")

    return matrices


def build_class_support_table(y):
    """
    Count how many target days fall into each regime label.

    Why it exists: section 6.7 requires class support reported alongside
    every metric -- this is the one place that count is computed, so
    every model's/baseline's confusion matrix row totals can be checked
    against it.

    Parameters:
        y: pandas.Series of str, the target from assemble_dataset().

    Returns:
        pandas.DataFrame, columns regime_label, n_target_days, in
        config.ML_REGIME_LABEL_ORDER order. Also written to
        config.ML_CLASS_SUPPORT_TABLE_PATH.
    """
    support = y.value_counts().reindex(config.ML_REGIME_LABEL_ORDER, fill_value=0)
    support_df = support.rename_axis("regime_label").reset_index(name="n_target_days")
    config.OUTPUTS_TABLES_DIR.mkdir(parents=True, exist_ok=True)
    support_df.to_csv(config.ML_CLASS_SUPPORT_TABLE_PATH, index=False)
    print(f"[model] class support -> {config.ML_CLASS_SUPPORT_TABLE_PATH}")
    return support_df


def main():
    """
    Run the full Phase 8 pipeline: assemble the dataset, walk-forward
    evaluate both baselines and both models, write every table section
    6.7 requires, and render figures 8 and 9.

    Why it exists: this is the entry point src/run_all.py calls for
    Phase 8 (BUILD-SPEC section 12). Opens its own connection to
    config.DB_PATH, same pattern as every phase since Phase 4. Calls
    charts.plot_confusion_matrices() and charts.plot_decision_tree()
    directly here rather than from charts.main(), the same reasoning
    src/regimes.py uses for its before/after diagnostic chart: the fitted
    model objects and in-memory confusion-matrix arrays this needs don't
    persist to disk in a form charts.py could reconstruct on its own. See
    docs/decisions-log.md.

    Parameters:
        None.

    Returns:
        None.
    """
    panel = load_panel()

    conn = sqlite3.connect(config.DB_PATH)
    try:
        X, y, current_regime_label = assemble_dataset(conn, panel)

        oof_predictions_df, fold_metrics_df = run_walk_forward_evaluation(X, y, current_regime_label)
        build_model_comparison_table(oof_predictions_df, config.ML_REGIME_LABEL_ORDER)
        confusion_matrices = build_confusion_matrices(oof_predictions_df, config.ML_REGIME_LABEL_ORDER)
        build_class_support_table(y)

        # Illustrative-only: fit one more depth-config.ML_TREE_MAX_DEPTH
        # tree on the FULL dataset purely so figure 9 has something
        # legible to draw. This tree is never scored and never appears in
        # ml_model_comparison.csv -- fitting and evaluating on the same
        # data would defeat the entire point of the walk-forward
        # evaluation above. See docs/decisions-log.md.
        illustrative_tree = build_decision_tree_model()
        illustrative_tree.fit(X, y)

        charts.plot_confusion_matrices(confusion_matrices, config.ML_REGIME_LABEL_ORDER)
        charts.plot_decision_tree(illustrative_tree, list(X.columns), config.ML_REGIME_LABEL_ORDER)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
    sys.exit(0)
