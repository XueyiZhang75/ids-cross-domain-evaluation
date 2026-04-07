"""
feature_table_audit.py — Audit multiple feature parquets for ML readiness.

Checks schema consistency, NaN/inf counts, label distributions, and
match/ambiguous flag status across a set of feature tables.
"""

from pathlib import Path

import numpy as np
import pandas as pd

from src.features.extract_flow_features import META_COLS, get_feature_columns
from src.utils.logging_utils import get_logger

logger = get_logger(__name__)


def audit_single(path: str | Path) -> dict:
    """Audit one feature parquet and return a report dict."""
    path = Path(path)
    df = pd.read_parquet(path)
    feat_cols = get_feature_columns(df)
    feat_df = df[feat_cols]

    report = {
        "file": path.name,
        "rows": len(df),
        "total_columns": len(df.columns),
        "feature_columns": len(feat_cols),
        "feature_names": feat_cols,
        "nan_count": int(feat_df.isna().sum().sum()),
        "inf_count": int(np.isinf(feat_df.select_dtypes(include="number")).sum().sum()),
    }

    # Label distribution.
    if "binary_label" in df.columns:
        report["binary_label"] = df["binary_label"].value_counts(dropna=False).to_dict()
    if "matched_flag" in df.columns:
        report["matched_flag"] = df["matched_flag"].value_counts().to_dict()
    if "ambiguous_flag" in df.columns:
        report["ambiguous_flag"] = df["ambiguous_flag"].value_counts().to_dict()

    # Check for missing expected meta columns.
    missing_meta = [c for c in META_COLS if c not in df.columns]
    report["missing_meta_cols"] = missing_meta

    return report


def audit_multiple(paths: list[str | Path]) -> dict:
    """Audit a list of feature parquets and check cross-file consistency."""
    reports = [audit_single(p) for p in paths]

    # Schema consistency: compare feature column names.
    all_feat_names = [tuple(r["feature_names"]) for r in reports]
    schema_consistent = len(set(all_feat_names)) == 1

    return {
        "files": reports,
        "schema_consistent": schema_consistent,
        "common_feature_count": reports[0]["feature_columns"] if schema_consistent else None,
    }
