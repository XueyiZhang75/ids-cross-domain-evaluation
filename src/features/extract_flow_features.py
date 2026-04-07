"""
extract_flow_features.py — Derive ML-ready features from a labeled flow table.

Reads a labeled flow parquet (output of the label aligner) and produces a
feature parquet with:
    - basic numeric features (from flow table)
    - derived ratio/rate features
    - protocol indicators
    - metadata and label columns (preserved, not used as features)

No normalization or scaling is applied here — that happens downstream,
fitted on the training split only (see pipeline_guardrails.md).
"""

from pathlib import Path

import pandas as pd

from src.utils.logging_utils import get_logger

logger = get_logger(__name__)

# Columns that are metadata / labels — preserved in output but NOT features.
META_COLS = [
    "flow_id", "pcap_file", "start_time", "end_time",
    "matched_flag", "ambiguous_flag", "label_match_method",
    "original_label", "binary_label", "coarse_family",
]


def extract_features(df: pd.DataFrame) -> pd.DataFrame:
    """Derive features from a labeled flow DataFrame.

    Parameters
    ----------
    df : DataFrame
        A labeled flow table (output of flow_label_aligner).

    Returns
    -------
    DataFrame
        Feature table with metadata, label, and feature columns.
    """
    out = pd.DataFrame()

    # ── Metadata / labels ───────────────────────────────────────────────
    for col in META_COLS:
        if col in df.columns:
            out[col] = df[col]

    # ── Basic numeric features ──────────────────────────────────────────
    out["duration_s"] = df["duration_s"]
    out["packet_count_total"] = df["packet_count_total"]
    out["bytes_total"] = df["bytes_total"]
    out["packet_count_fwd"] = df["packet_count_fwd"]
    out["packet_count_bwd"] = df["packet_count_bwd"]
    out["bytes_fwd"] = df["bytes_fwd"]
    out["bytes_bwd"] = df["bytes_bwd"]

    # ── Protocol indicators ─────────────────────────────────────────────
    out["protocol"] = df["protocol"]
    out["is_tcp"] = (df["protocol"] == 6).astype(int)
    out["is_udp"] = (df["protocol"] == 17).astype(int)

    # ── Derived features ────────────────────────────────────────────────
    # Safe division helper: returns 0.0 where denominator is 0.
    def _safe_div(num, den):
        return num.div(den).fillna(0.0).replace([float("inf"), float("-inf")], 0.0)

    out["bytes_per_packet"] = _safe_div(df["bytes_total"], df["packet_count_total"])
    out["bytes_per_packet_fwd"] = _safe_div(df["bytes_fwd"], df["packet_count_fwd"])
    out["bytes_per_packet_bwd"] = _safe_div(df["bytes_bwd"], df["packet_count_bwd"])

    out["packets_per_second"] = _safe_div(df["packet_count_total"], df["duration_s"])
    out["bytes_per_second"] = _safe_div(df["bytes_total"], df["duration_s"])

    out["fwd_packet_ratio"] = _safe_div(df["packet_count_fwd"], df["packet_count_total"])
    out["bwd_packet_ratio"] = _safe_div(df["packet_count_bwd"], df["packet_count_total"])
    out["fwd_byte_ratio"] = _safe_div(df["bytes_fwd"], df["bytes_total"])
    out["bwd_byte_ratio"] = _safe_div(df["bytes_bwd"], df["bytes_total"])

    return out


def get_feature_columns(df: pd.DataFrame) -> list[str]:
    """Return the list of numeric feature column names (excluding metadata/labels)."""
    return [c for c in df.columns if c not in META_COLS]


def run(
    input_path: str | Path,
    output_path: str | Path,
) -> dict:
    """Read labeled flow parquet, extract features, write feature parquet.

    Returns a report dict.
    """
    input_path = Path(input_path)
    output_path = Path(output_path)

    logger.info("Loading labeled flows: %s", input_path.name)
    df = pd.read_parquet(input_path)
    logger.info("  %d rows", len(df))

    features = extract_features(df)

    # Sanity check for inf / NaN in feature columns.
    feat_cols = get_feature_columns(features)
    n_inf = features[feat_cols].isin([float("inf"), float("-inf")]).sum().sum()
    n_nan = features[feat_cols].isna().sum().sum()
    if n_inf > 0:
        logger.warning("  %d inf values detected in features — replaced with 0", n_inf)
        features[feat_cols] = features[feat_cols].replace(
            [float("inf"), float("-inf")], 0.0
        )
    if n_nan > 0:
        logger.warning("  %d NaN values detected in features — filled with 0", n_nan)
        features[feat_cols] = features[feat_cols].fillna(0.0)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    features.to_parquet(output_path, index=False)
    logger.info("Feature table written -> %s (%d rows, %d feature cols)",
                output_path, len(features), len(feat_cols))

    return {
        "input_file": input_path.name,
        "output_file": str(output_path),
        "rows": len(features),
        "feature_columns": len(feat_cols),
        "feature_names": feat_cols,
        "inf_replaced": int(n_inf),
        "nan_filled": int(n_nan),
    }
