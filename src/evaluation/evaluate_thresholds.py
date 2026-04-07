"""
evaluate_thresholds.py — Threshold sweep and fixed-FPR evaluation.

Reads a predictions parquet (with model_name, y_true, y_score columns)
and produces per-model threshold analysis.
"""

import numpy as np
import pandas as pd
from sklearn.metrics import precision_score, recall_score, f1_score

from src.utils.logging_utils import get_logger

logger = get_logger(__name__)


def _metrics_at_threshold(y_true: np.ndarray, y_score: np.ndarray,
                          threshold: float) -> dict:
    """Compute metrics for a single threshold."""
    y_pred = (y_score >= threshold).astype(int)
    n_pos = y_true.sum()
    n_neg = len(y_true) - n_pos
    fp = ((y_pred == 1) & (y_true == 0)).sum()
    fpr = fp / n_neg if n_neg > 0 else 0.0

    return {
        "threshold": threshold,
        "precision": precision_score(y_true, y_pred, zero_division=0),
        "recall": recall_score(y_true, y_pred, zero_division=0),
        "f1": f1_score(y_true, y_pred, zero_division=0),
        "fpr": fpr,
        "tp": int(((y_pred == 1) & (y_true == 1)).sum()),
        "fp": int(fp),
        "fn": int(((y_pred == 0) & (y_true == 1)).sum()),
        "tn": int(((y_pred == 0) & (y_true == 0)).sum()),
    }


def threshold_sweep(y_true: np.ndarray, y_score: np.ndarray,
                    n_points: int = 200) -> list[dict]:
    """Evaluate metrics across a grid of thresholds."""
    thresholds = np.linspace(0, 1, n_points + 1)
    return [_metrics_at_threshold(y_true, y_score, t) for t in thresholds]


def best_f1_threshold(sweep: list[dict]) -> dict:
    """Return the sweep entry with the highest F1."""
    return max(sweep, key=lambda x: x["f1"])


def threshold_at_fixed_fpr(y_true: np.ndarray, y_score: np.ndarray,
                           target_fpr: float) -> dict | None:
    """Find the highest threshold that achieves FPR <= target_fpr.

    Scans unique score values as candidate thresholds for precision.
    Returns metrics at that threshold, or None if not achievable.
    """
    n_neg = (y_true == 0).sum()
    if n_neg == 0:
        return None

    # Use sorted unique scores as candidate thresholds (descending).
    candidates = np.sort(np.unique(y_score))[::-1]

    best = None
    for t in candidates:
        m = _metrics_at_threshold(y_true, y_score, t)
        if m["fpr"] <= target_fpr:
            best = m
            break  # first (highest) threshold meeting the budget

    if best is None:
        # Even the highest threshold doesn't meet the FPR budget.
        # Use the max score + epsilon.
        best = _metrics_at_threshold(y_true, y_score, float(y_score.max()) + 1e-9)
        best["note"] = "FPR budget not achievable; threshold set above max score"

    best["target_fpr"] = target_fpr
    return best


def analyze_model(y_true: np.ndarray, y_score: np.ndarray,
                  model_name: str,
                  fpr_budgets: list[float] = None) -> dict:
    """Full threshold analysis for one model."""
    if fpr_budgets is None:
        fpr_budgets = [0.01, 0.005, 0.001]

    sweep = threshold_sweep(y_true, y_score)
    default = _metrics_at_threshold(y_true, y_score, 0.5)
    best_f1 = best_f1_threshold(sweep)

    fixed_fpr_results = []
    for budget in fpr_budgets:
        r = threshold_at_fixed_fpr(y_true, y_score, budget)
        if r:
            fixed_fpr_results.append(r)

    return {
        "model_name": model_name,
        "default_threshold": default,
        "best_f1_threshold": best_f1,
        "fixed_fpr": fixed_fpr_results,
    }
