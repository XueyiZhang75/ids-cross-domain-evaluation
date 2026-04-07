"""
apply_label_mapping.py — Apply label_mapping_master.csv to label-reference CSVs.

This module loads the master mapping table, filters it for a given dataset,
and checks whether every original label in the label-reference CSVs can be
matched to a mapping entry.

It does NOT perform flow-level label alignment — only CSV-level consistency
checking between the mapping table and the label-reference files.
"""

import re
from pathlib import Path

import pandas as pd

from src.utils.logging_utils import get_logger

logger = get_logger(__name__)

# Characters that should all be treated as a plain ASCII hyphen for matching.
# Includes cp1252 en-dash (\x96), Unicode en-dash, em-dash, minus sign.
_DASH_PATTERN = re.compile(r"[\x96\u2013\u2014\u2212]")


# ---------------------------------------------------------------------------
# Label string normalisation
# ---------------------------------------------------------------------------

def normalise_label(label: str) -> str:
    """Minimal normalisation for matching labels across CSV and mapping table.

    Steps (conservative — only handles known issues):
    1. Strip leading/trailing whitespace.
    2. Replace dash-like characters (cp1252 en-dash, Unicode dashes) with
       ASCII hyphen.
    """
    s = label.strip()
    s = _DASH_PATTERN.sub("-", s)
    return s


# ---------------------------------------------------------------------------
# Mapping table loading
# ---------------------------------------------------------------------------

def load_mapping(
    mapping_path: str | Path,
    dataset_name: str,
) -> dict[str, dict]:
    """Load the master mapping CSV and return entries for *dataset_name*.

    Returns a dict keyed by normalised original_label, with each value being
    a dict of the mapping fields (binary_label, coarse_family, etc.).
    """
    mapping_path = Path(mapping_path)
    if not mapping_path.is_file():
        raise FileNotFoundError(f"Mapping file not found: {mapping_path}")

    df = pd.read_csv(mapping_path, encoding="utf-8")
    df.columns = df.columns.str.strip()

    # Filter to requested dataset.
    mask = df["dataset_name"] == dataset_name
    ds_df = df[mask].copy()

    if ds_df.empty:
        logger.warning("No mapping entries found for dataset '%s'", dataset_name)
        return {}

    logger.info("Loaded %d mapping entries for '%s'", len(ds_df), dataset_name)

    # Build lookup keyed by normalised label.
    mapping = {}
    for _, row in ds_df.iterrows():
        key = normalise_label(str(row["original_label"]))
        mapping[key] = {
            "original_label": row["original_label"],
            "binary_label": row["binary_label"],
            "coarse_family": row.get("coarse_family", ""),
            "keep_or_exclude": row.get("keep_or_exclude", "keep"),
        }
    return mapping


# ---------------------------------------------------------------------------
# Per-CSV mapping check
# ---------------------------------------------------------------------------

def check_mapping_for_csv(
    df: pd.DataFrame,
    label_col: str,
    mapping: dict[str, dict],
    filename: str = "",
) -> dict:
    """Check whether all labels in *df[label_col]* match the mapping.

    Returns a report dict with matched/unmatched labels and counts by
    binary_label and coarse_family.
    """
    raw_labels = df[label_col].dropna().unique().tolist()
    normalised = {normalise_label(str(l)): str(l) for l in raw_labels}

    matched = {}      # normalised -> mapping entry
    unmatched = {}     # normalised -> raw string

    for norm, raw in normalised.items():
        if norm in mapping:
            matched[norm] = mapping[norm]
        else:
            unmatched[norm] = raw

    # Count rows per binary_label.
    binary_counts: dict[str, int] = {}
    family_counts: dict[str, int] = {}
    unmatched_row_count = 0

    for raw_label in df[label_col].dropna():
        norm = normalise_label(str(raw_label))
        entry = mapping.get(norm)
        if entry:
            bl = entry["binary_label"]
            cf = entry["coarse_family"]
            binary_counts[bl] = binary_counts.get(bl, 0) + 1
            if cf and isinstance(cf, str) and cf.strip():
                family_counts[cf] = family_counts.get(cf, 0) + 1
        else:
            unmatched_row_count += 1

    return {
        "filename": filename,
        "total_rows": len(df),
        "label_unique_count": len(raw_labels),
        "matched_labels": list(matched.keys()),
        "unmatched_labels": {k: v for k, v in unmatched.items()},
        "binary_label_counts": binary_counts,
        "coarse_family_counts": family_counts,
        "unmatched_row_count": unmatched_row_count,
    }
