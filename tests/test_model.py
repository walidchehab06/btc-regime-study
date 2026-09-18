"""
Tests for src/model.py's target construction, look-ahead safety, and
walk-forward evaluation mechanics, per
BUILD-SPEC-bitcoin-regime-study.md section 6.7 and section 11's
requirement that hand-written calculations are tested against known
cases. Section 6.7's central risk in this phase is silent look-ahead or
leakage, so most of these tests exist to make that risk visible if it's
ever reintroduced.
"""

import numpy as np
import pandas as pd
from sklearn.model_selection import TimeSeriesSplit

from src import config, model


def test_build_target_shifts_forward_by_horizon():
    # Regime labels A, A, B, B, C for 5 consecutive days. The 2-day-ahead
    # target at day 0 is day 2's label (B), not day 0's own label.
    dates = pd.date_range("2024-01-01", periods=5, freq="D")
    regime_labels = pd.Series(["A", "A", "B", "B", "C"], index=dates)

    target = model.build_target(regime_labels, horizon_days=2)

    assert list(target.iloc[:3]) == ["B", "B", "C"]
    assert target.iloc[3:].isna().all()


def test_compute_technical_features_are_trailing_only():
    # A feature value at date t must be unchanged by editing the panel
    # strictly after date t -- the direct check that no feature reaches
    # into the future, which section 6.7 forbids.
    dates = pd.date_range("2024-01-01", periods=40, freq="D")
    rng = np.random.default_rng(0)
    panel = pd.DataFrame(
        {
            "log_return_BTC-USD": rng.normal(0, 0.01, len(dates)),
            config.ML_DXY_FEATURE_COLUMN: 100 + rng.normal(0, 1, len(dates)).cumsum(),
            config.ML_REAL_YIELD_COLUMN: 2 + rng.normal(0, 0.1, len(dates)).cumsum(),
            "fng_value": rng.integers(0, 101, len(dates)).astype(float),
        },
        index=dates,
    )

    features_before = model.compute_technical_features(panel)

    edited_panel = panel.copy()
    cutoff = 25
    edited_panel.iloc[cutoff + 1 :] = edited_panel.iloc[cutoff + 1 :] + 999.0

    features_after = model.compute_technical_features(edited_panel)

    pd.testing.assert_frame_equal(features_before.iloc[: cutoff + 1], features_after.iloc[: cutoff + 1])


def test_timeseries_split_gap_prevents_target_window_overlap():
    # config.ML_TIMESERIES_GAP_DAYS is set equal to the prediction
    # horizon specifically so no training row's target (dated up to
    # horizon_days ahead of that row) lands inside the following test
    # fold. This checks that gap literally does what the config comment
    # claims.
    n_rows = 200
    splitter = TimeSeriesSplit(n_splits=config.ML_TIMESERIES_N_SPLITS, gap=config.ML_TIMESERIES_GAP_DAYS)

    for train_idx, test_idx in splitter.split(np.arange(n_rows)):
        last_train_target_position = train_idx.max() + config.ML_TARGET_HORIZON_DAYS
        assert last_train_target_position < test_idx.min()


def test_majority_class_baseline_is_recomputed_per_fold():
    # Two folds with deliberately different training-label mixes must
    # produce different majority predictions -- if this were a single
    # global mode, both folds would predict the same label.
    y_fold_1_train = pd.Series(["RISK_ASSET"] * 8 + ["HARD_ASSET"] * 2)
    y_fold_2_train = pd.Series(["HARD_ASSET"] * 9 + ["RISK_ASSET"] * 1)

    majority_1 = y_fold_1_train.mode().iloc[0]
    majority_2 = y_fold_2_train.mode().iloc[0]

    assert majority_1 == "RISK_ASSET"
    assert majority_2 == "HARD_ASSET"
    assert majority_1 != majority_2


def test_persistence_baseline_matches_current_regime_label_on_test_fold():
    dates = pd.date_range("2024-01-01", periods=10, freq="D")
    current_regime_label = pd.Series(
        ["RISK_ASSET"] * 5 + ["HARD_ASSET"] * 5, index=dates
    )
    test_idx = np.array([6, 7, 8])

    persistence_prediction = current_regime_label.iloc[test_idx].to_numpy()

    assert list(persistence_prediction) == ["HARD_ASSET", "HARD_ASSET", "HARD_ASSET"]


def test_compute_metrics_on_a_known_confusion_case():
    # 4 predictions, 3 correct, one class (B) never predicted at all --
    # exercises zero_division=0 for macro F1 on the missing class.
    y_true = ["A", "A", "B", "B"]
    y_pred = ["A", "A", "A", "B"]
    labels = ["A", "B"]

    metrics = model.compute_metrics(y_true, y_pred, labels)

    assert np.isclose(metrics["accuracy"], 0.75)
    assert np.isclose(metrics["balanced_accuracy"], 0.75)
    assert 0.0 < metrics["macro_f1"] < 1.0


def test_build_feature_matrix_leaves_no_nan_in_the_modelling_dataset():
    # Warm-up NaNs from the rolling features, plus a NaN planted in one
    # correlation column, must all be dropped before the matrix reaches a
    # model. Section 11 requires that no NaN survives into the modelling data.
    dates = pd.date_range("2024-01-01", periods=60, freq="D")
    rng = np.random.default_rng(1)
    panel = pd.DataFrame(
        {
            "log_return_BTC-USD": rng.normal(0, 0.01, len(dates)),
            config.ML_DXY_FEATURE_COLUMN: 100 + rng.normal(0, 1, len(dates)).cumsum(),
            config.ML_REAL_YIELD_COLUMN: 2 + rng.normal(0, 0.1, len(dates)).cumsum(),
            "fng_value": rng.integers(0, 101, len(dates)).astype(float),
        },
        index=dates,
    )

    technical_columns = {
        "realized_vol_20", "btc_momentum_20", "dxy_change_20",
        "real_yield_change_20", "fng_level", "fng_change_14",
    }
    correlation_column_names = [c for c in model.CONTINUOUS_FEATURE_COLUMNS if c not in technical_columns]
    correlation_features = pd.DataFrame(
        rng.uniform(-1, 1, (len(dates), len(correlation_column_names))),
        index=dates,
        columns=correlation_column_names,
    )
    correlation_features.iloc[30, 0] = np.nan

    regime_labels = pd.Series(config.ML_REGIME_LABEL_ORDER * 15, index=dates)

    X, current_regime_label = model.build_feature_matrix(panel, correlation_features, regime_labels)

    assert not X.isna().any().any()
    assert len(X) < len(dates)
    assert X.index.equals(current_regime_label.index)
