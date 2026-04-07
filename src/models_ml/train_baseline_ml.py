"""
train_baseline_ml.py — Train and evaluate binary ML baselines on flow features.

Supports Logistic Regression, Random Forest, and XGBoost.
Reads feature parquets, filters to clean labeled samples, splits by capture
day (pcap_file), trains on the training split, evaluates on the test split.
"""

from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import (
    accuracy_score, precision_score, recall_score, f1_score, roc_auc_score,
)
import xgboost as xgb

from src.features.extract_flow_features import META_COLS, get_feature_columns
from src.utils.io_utils import load_yaml
from src.utils.logging_utils import get_logger

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Data loading and filtering
# ---------------------------------------------------------------------------

def load_and_filter(paths: list[str | Path]) -> pd.DataFrame:
    """Load feature parquets, concatenate, and filter to clean labeled rows."""
    frames = []
    for p in paths:
        df = pd.read_parquet(p)
        df["_source_file"] = Path(p).stem
        frames.append(df)
    combined = pd.concat(frames, ignore_index=True)
    logger.info("Loaded %d total rows from %d files", len(combined), len(paths))

    # Filter to supervised-ready rows.
    mask = (
        (combined["matched_flag"] == True) &
        (combined["ambiguous_flag"] == False) &
        (combined["binary_label"].isin(["benign", "attack"]))
    )
    clean = combined[mask].copy()
    logger.info("After filtering: %d rows (dropped %d unresolved)",
                len(clean), len(combined) - len(clean))
    return clean


# ---------------------------------------------------------------------------
# Split by capture day
# ---------------------------------------------------------------------------

def split_by_day(
    df: pd.DataFrame,
    test_days: list[str],
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Split into train/test by pcap_file substring matching.

    Parameters
    ----------
    test_days : list of str
        Substrings to match against pcap_file for test set assignment.
        E.g., ["Friday"] means any row whose pcap_file contains "Friday"
        goes to test; everything else goes to train.
    """
    test_mask = df["pcap_file"].str.lower().apply(
        lambda x: any(d.lower() in x for d in test_days)
    )
    train = df[~test_mask].copy()
    test = df[test_mask].copy()
    return train, test


# ---------------------------------------------------------------------------
# Model training and evaluation
# ---------------------------------------------------------------------------

def _encode_labels(y: pd.Series) -> np.ndarray:
    return (y == "attack").astype(int).values


def train_and_eval(
    X_train: np.ndarray,
    y_train: np.ndarray,
    X_test: np.ndarray,
    y_test: np.ndarray,
    model_name: str,
    config: dict,
) -> dict:
    """Train one model and return metrics."""

    if model_name == "logistic_regression":
        cfg = config.get("logistic_regression", {})
        model = LogisticRegression(
            solver=cfg.get("solver", "lbfgs"),
            max_iter=cfg.get("max_iter", 1000),
            C=cfg.get("C", 1.0),
            class_weight=cfg.get("class_weight", "balanced"),
            random_state=cfg.get("random_state", 42),
        )
        # LR needs scaling.
        scaler = StandardScaler()
        X_train = scaler.fit_transform(X_train)
        X_test = scaler.transform(X_test)
        model.fit(X_train, y_train)

    elif model_name == "random_forest":
        cfg = config.get("random_forest", {})
        model = RandomForestClassifier(
            n_estimators=cfg.get("n_estimators", 200),
            max_depth=cfg.get("max_depth", None),
            min_samples_split=cfg.get("min_samples_split", 5),
            min_samples_leaf=cfg.get("min_samples_leaf", 2),
            class_weight=cfg.get("class_weight", "balanced"),
            n_jobs=cfg.get("n_jobs", -1),
            random_state=cfg.get("random_state", 42),
        )
        model.fit(X_train, y_train)

    elif model_name == "xgboost":
        cfg = config.get("xgboost", {})
        model = xgb.XGBClassifier(
            n_estimators=cfg.get("n_estimators", 300),
            max_depth=cfg.get("max_depth", 6),
            learning_rate=cfg.get("learning_rate", 0.1),
            subsample=cfg.get("subsample", 0.8),
            colsample_bytree=cfg.get("colsample_bytree", 0.8),
            scale_pos_weight=cfg.get("scale_pos_weight", 1.0),
            eval_metric=cfg.get("eval_metric", "logloss"),
            random_state=cfg.get("random_state", 42),
            use_label_encoder=False,
        )
        model.fit(X_train, y_train)

    else:
        raise ValueError(f"Unknown model: {model_name}")

    # Predict.
    y_pred = model.predict(X_test)
    y_prob = model.predict_proba(X_test)[:, 1] if hasattr(model, "predict_proba") else None

    # Metrics.
    metrics = {
        "model": model_name,
        "accuracy": accuracy_score(y_test, y_pred),
        "precision": precision_score(y_test, y_pred, zero_division=0),
        "recall": recall_score(y_test, y_pred, zero_division=0),
        "f1": f1_score(y_test, y_pred, zero_division=0),
        "y_pred": y_pred,
        "y_score": y_prob,
    }
    if y_prob is not None and len(np.unique(y_test)) == 2:
        metrics["roc_auc"] = roc_auc_score(y_test, y_prob)
    else:
        metrics["roc_auc"] = None

    return metrics


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def run(
    feature_paths: list[str | Path],
    model_config_path: str | Path,
    test_days: list[str],
) -> dict:
    """End-to-end: load data, split, train all baselines, return results."""

    config = load_yaml(model_config_path)

    # Load and filter.
    df = load_and_filter(feature_paths)
    feat_cols = [c for c in get_feature_columns(df) if c != "_source_file"]
    logger.info("Feature columns (%d): %s", len(feat_cols), feat_cols)

    # Split.
    train_df, test_df = split_by_day(df, test_days)
    logger.info("Train: %d rows  |  Test: %d rows", len(train_df), len(test_df))

    # Encode.
    y_train = _encode_labels(train_df["binary_label"])
    y_test = _encode_labels(test_df["binary_label"])
    X_train = train_df[feat_cols].values.astype(float)
    X_test = test_df[feat_cols].values.astype(float)

    # Class distribution.
    train_dist = dict(zip(*np.unique(y_train, return_counts=True)))
    test_dist = dict(zip(*np.unique(y_test, return_counts=True)))
    logger.info("Train class dist: %s", train_dist)
    logger.info("Test  class dist: %s", test_dist)

    # Train each baseline and collect predictions.
    results = []
    predictions_frames = []
    for name in ["logistic_regression", "random_forest", "xgboost"]:
        logger.info("Training %s ...", name)
        m = train_and_eval(X_train, y_train, X_test, y_test, name, config)
        results.append(m)
        logger.info("  %s -> Acc=%.4f  P=%.4f  R=%.4f  F1=%.4f  AUC=%s",
                     name, m["accuracy"], m["precision"], m["recall"],
                     m["f1"], f"{m['roc_auc']:.4f}" if m["roc_auc"] else "N/A")

        # Build per-model prediction frame.
        pred_df = pd.DataFrame({
            "model_name": name,
            "y_true": y_test,
            "y_score": m["y_score"] if m["y_score"] is not None else np.nan,
            "y_pred_default": m["y_pred"],
            "pcap_file": test_df["pcap_file"].values,
        })
        predictions_frames.append(pred_df)

    all_predictions = pd.concat(predictions_frames, ignore_index=True)

    return {
        "feature_columns": feat_cols,
        "train_rows": len(train_df),
        "test_rows": len(test_df),
        "train_class_dist": train_dist,
        "test_class_dist": test_dist,
        "test_days": test_days,
        "models": results,
        "predictions": all_predictions,
    }
