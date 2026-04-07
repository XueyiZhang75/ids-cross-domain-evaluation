"""
flow_label_join_check.py — Join feasibility analysis between flow tables
and label-reference CSVs.

This module does NOT perform real label assignment. It only checks how well
the keys in a flow table (from our PCAP extraction) can be matched against
the keys in a CICFlowMeter-generated label-reference CSV.

Two join strategies are compared:
    1. Directional 5-tuple  (src_ip, src_port, dst_ip, dst_port, protocol)
    2. Canonical 5-tuple    (min_ip, min_port, max_ip, max_port, protocol)
       — direction-agnostic, matching our bidirectional flow definition.
"""

from pathlib import Path

import pandas as pd

from src.utils.logging_utils import get_logger

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Key construction helpers
# ---------------------------------------------------------------------------

def _directional_key(row: pd.Series, src_ip: str, src_port: str,
                     dst_ip: str, dst_port: str, proto: str) -> tuple:
    return (str(row[src_ip]), int(row[src_port]),
            str(row[dst_ip]), int(row[dst_port]), int(row[proto]))


def _canonical_key(row: pd.Series, src_ip: str, src_port: str,
                   dst_ip: str, dst_port: str, proto: str) -> tuple:
    a = (str(row[src_ip]), int(row[src_port]))
    b = (str(row[dst_ip]), int(row[dst_port]))
    p = int(row[proto])
    if a <= b:
        return (a[0], a[1], b[0], b[1], p)
    return (b[0], b[1], a[0], a[1], p)


def build_key_set(df: pd.DataFrame, src_ip: str, src_port: str,
                  dst_ip: str, dst_port: str, proto: str,
                  canonical: bool = False) -> set[tuple]:
    """Build a set of 5-tuple keys from a DataFrame."""
    keys = set()
    for _, row in df.iterrows():
        try:
            if canonical:
                keys.add(_canonical_key(row, src_ip, src_port,
                                        dst_ip, dst_port, proto))
            else:
                keys.add(_directional_key(row, src_ip, src_port,
                                          dst_ip, dst_port, proto))
        except (ValueError, TypeError):
            continue
    return keys


# ---------------------------------------------------------------------------
# Main analysis
# ---------------------------------------------------------------------------

def run_join_check(
    flow_path: str | Path,
    label_csv_path: str | Path,
) -> dict:
    """Compare join strategies between a flow parquet and a label-ref CSV.

    Returns a report dict with match counts and rates.
    """
    flow_path = Path(flow_path)
    label_csv_path = Path(label_csv_path)

    # Load flow table.
    logger.info("Loading flow table: %s", flow_path.name)
    flows = pd.read_parquet(flow_path)
    logger.info("  Flow table: %d rows", len(flows))

    # Load label reference CSV.
    logger.info("Loading label reference: %s", label_csv_path.name)
    for enc in ("utf-8", "latin-1"):
        try:
            labels = pd.read_csv(label_csv_path, encoding=enc,
                                 on_bad_lines="skip", low_memory=False)
            break
        except UnicodeDecodeError:
            continue
    else:
        raise ValueError(f"Could not decode {label_csv_path.name}")

    labels.columns = labels.columns.str.strip()
    logger.info("  Label reference: %d rows", len(labels))

    # --- Strategy 1: Directional 5-tuple ---
    flow_dir_keys = build_key_set(
        flows, "src_ip", "src_port", "dst_ip", "dst_port", "protocol",
        canonical=False,
    )
    label_dir_keys = build_key_set(
        labels, "Source IP", "Source Port", "Destination IP",
        "Destination Port", "Protocol", canonical=False,
    )
    dir_intersect = flow_dir_keys & label_dir_keys

    # --- Strategy 2: Canonical (bidirectional) 5-tuple ---
    flow_canon_keys = build_key_set(
        flows, "src_ip", "src_port", "dst_ip", "dst_port", "protocol",
        canonical=True,
    )
    label_canon_keys = build_key_set(
        labels, "Source IP", "Source Port", "Destination IP",
        "Destination Port", "Protocol", canonical=True,
    )
    canon_intersect = flow_canon_keys & label_canon_keys

    # --- Timestamp analysis ---
    ts_info = {}
    if "Timestamp" in labels.columns:
        ts_sample = labels["Timestamp"].dropna().head(5).tolist()
        ts_info = {
            "timestamp_column": "Timestamp",
            "sample_values": ts_sample,
            "note": "Timestamp is present; could be used for time-window "
                    "matching in formal alignment.",
        }

    report = {
        "flow_file": flow_path.name,
        "label_file": label_csv_path.name,
        "flow_rows": len(flows),
        "label_rows": len(labels),
        "directional": {
            "flow_unique_keys": len(flow_dir_keys),
            "label_unique_keys": len(label_dir_keys),
            "matched_keys": len(dir_intersect),
            "match_rate_of_flow_keys": (
                len(dir_intersect) / len(flow_dir_keys) * 100
                if flow_dir_keys else 0
            ),
            "match_rate_of_label_keys": (
                len(dir_intersect) / len(label_dir_keys) * 100
                if label_dir_keys else 0
            ),
        },
        "canonical": {
            "flow_unique_keys": len(flow_canon_keys),
            "label_unique_keys": len(label_canon_keys),
            "matched_keys": len(canon_intersect),
            "match_rate_of_flow_keys": (
                len(canon_intersect) / len(flow_canon_keys) * 100
                if flow_canon_keys else 0
            ),
            "match_rate_of_label_keys": (
                len(canon_intersect) / len(label_canon_keys) * 100
                if label_canon_keys else 0
            ),
        },
        "timestamp_info": ts_info,
    }
    return report
