"""
flow_label_aligner.py — Assign labels from a label-reference CSV to a flow table.

Uses canonical (direction-agnostic) 5-tuple as the join key.
If the same canonical key maps to conflicting labels in the reference CSV,
the flow is marked as ambiguous rather than receiving a forced assignment.

This module does NOT do time-window matching (may be added later for
disambiguation of same-key flows with different labels across time).
"""

from pathlib import Path

import pandas as pd

from src.labeling.apply_label_mapping import load_mapping, normalise_label
from src.utils.logging_utils import get_logger

logger = get_logger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
MAPPING_PATH = PROJECT_ROOT / "data" / "external" / "label_mapping_master.csv"


# ---------------------------------------------------------------------------
# Canonical key helpers
# ---------------------------------------------------------------------------

def _canonical_key_from_row(src_ip, src_port, dst_ip, dst_port, proto):
    a = (str(src_ip), int(src_port))
    b = (str(dst_ip), int(dst_port))
    p = int(proto)
    if a <= b:
        return (a[0], a[1], b[0], b[1], p)
    return (b[0], b[1], a[0], a[1], p)


# ---------------------------------------------------------------------------
# Build label lookup from reference CSV
# ---------------------------------------------------------------------------

def _read_label_csv(path: Path) -> pd.DataFrame:
    """Read a single label-reference CSV with encoding fallback."""
    for enc in ("utf-8", "latin-1"):
        try:
            df = pd.read_csv(path, encoding=enc,
                             on_bad_lines="skip", low_memory=False)
            return df
        except UnicodeDecodeError:
            continue
    raise ValueError(f"Could not decode {path.name}")


def build_label_lookup(
    label_csv_paths: str | Path | list[str | Path],
) -> tuple[dict[tuple, str], dict[tuple, set[str]], int]:
    """Read one or more label-reference CSVs and build a canonical-key -> label lookup.

    Parameters
    ----------
    label_csv_paths : path or list of paths
        One CSV path, or a list of CSV paths to merge before building the lookup.

    Returns
    -------
    clean_lookup : dict
        canonical_key -> original_label (only for keys with a single unique label).
    ambiguous_keys : dict
        canonical_key -> set of conflicting labels.
    total_rows : int
        Total number of rows across all CSVs.
    """
    # Normalise to list.
    if isinstance(label_csv_paths, (str, Path)):
        label_csv_paths = [label_csv_paths]
    label_csv_paths = [Path(p) for p in label_csv_paths]

    # Read and concatenate all CSVs.
    total_rows = 0
    key_to_labels: dict[tuple, set[str]] = {}

    for csv_path in label_csv_paths:
        logger.info("Loading label reference: %s", csv_path.name)
        df = _read_label_csv(csv_path)
        df.columns = df.columns.str.strip()
        n = len(df)
        total_rows += n
        logger.info("  %d rows loaded", n)

        for _, row in df.iterrows():
            try:
                key = _canonical_key_from_row(
                    row["Source IP"], row["Source Port"],
                    row["Destination IP"], row["Destination Port"],
                    row["Protocol"],
                )
            except (ValueError, TypeError, KeyError):
                continue

            label = row.get("Label", None)
            if pd.isna(label):
                continue
            label = str(label).strip()
            key_to_labels.setdefault(key, set()).add(label)

    # Split into clean vs ambiguous.
    clean_lookup: dict[tuple, str] = {}
    ambiguous_keys: dict[tuple, set[str]] = {}
    for key, labels in key_to_labels.items():
        if len(labels) == 1:
            clean_lookup[key] = next(iter(labels))
        else:
            ambiguous_keys[key] = labels

    logger.info("  Combined: %d total rows, %d unique canonical keys (clean: %d, ambiguous: %d)",
                total_rows, len(key_to_labels), len(clean_lookup), len(ambiguous_keys))
    return clean_lookup, ambiguous_keys, total_rows


# ---------------------------------------------------------------------------
# Align labels onto a flow table
# ---------------------------------------------------------------------------

def align_labels(
    flow_path: str | Path,
    label_csv_paths: str | Path | list[str | Path],
    dataset_name: str,
    output_path: str | Path,
) -> dict:
    """Read a flow parquet, join labels via canonical 5-tuple, write result.

    Parameters
    ----------
    label_csv_paths : path or list of paths
        One or more label-reference CSV files to merge before alignment.

    Returns a report dict.
    """
    flow_path = Path(flow_path)
    output_path = Path(output_path)

    # 1. Load flow table.
    logger.info("Loading flow table: %s", flow_path.name)
    flows = pd.read_parquet(flow_path)
    n_flows = len(flows)
    logger.info("  %d flows", n_flows)

    # 2. Build label lookup from reference CSV(s).
    clean_lookup, ambiguous_keys, label_rows = build_label_lookup(label_csv_paths)

    # 3. Load label mapping (binary_label, coarse_family).
    mapping = load_mapping(MAPPING_PATH, dataset_name)

    # 4. Compute canonical key for each flow.
    canon_keys = []
    for _, row in flows.iterrows():
        try:
            k = _canonical_key_from_row(
                row["src_ip"], row["src_port"],
                row["dst_ip"], row["dst_port"],
                row["protocol"],
            )
        except (ValueError, TypeError):
            k = None
        canon_keys.append(k)

    # 5. Look up and assign labels.
    matched_flags = []
    ambiguous_flags = []
    match_methods = []
    original_labels = []
    binary_labels = []
    coarse_families = []

    for key in canon_keys:
        if key is None:
            matched_flags.append(False)
            ambiguous_flags.append(False)
            match_methods.append("no_key")
            original_labels.append(None)
            binary_labels.append(None)
            coarse_families.append(None)
            continue

        if key in ambiguous_keys:
            matched_flags.append(False)
            ambiguous_flags.append(True)
            match_methods.append("ambiguous_canonical_5tuple")
            original_labels.append(None)
            binary_labels.append(None)
            coarse_families.append(None)
            continue

        if key in clean_lookup:
            raw_label = clean_lookup[key]
            norm = normalise_label(raw_label)
            entry = mapping.get(norm)
            matched_flags.append(True)
            ambiguous_flags.append(False)
            match_methods.append("canonical_5tuple")
            original_labels.append(raw_label)
            if entry:
                binary_labels.append(entry["binary_label"])
                cf = entry.get("coarse_family", "")
                coarse_families.append(cf if isinstance(cf, str) and cf.strip() else None)
            else:
                binary_labels.append(None)
                coarse_families.append(None)
        else:
            matched_flags.append(False)
            ambiguous_flags.append(False)
            match_methods.append("unmatched")
            original_labels.append(None)
            binary_labels.append(None)
            coarse_families.append(None)

    # 6. Attach columns.
    flows["matched_flag"] = matched_flags
    flows["ambiguous_flag"] = ambiguous_flags
    flows["label_match_method"] = match_methods
    flows["original_label"] = original_labels
    flows["binary_label"] = binary_labels
    flows["coarse_family"] = coarse_families

    # 7. Write output.
    output_path.parent.mkdir(parents=True, exist_ok=True)
    flows.to_parquet(output_path, index=False)
    logger.info("Labeled flow table written -> %s", output_path)

    # 8. Build report.
    n_matched = sum(matched_flags)
    n_ambiguous = sum(ambiguous_flags)
    n_unmatched = n_flows - n_matched - n_ambiguous

    binary_counts = {}
    for bl in binary_labels:
        if bl is not None:
            binary_counts[bl] = binary_counts.get(bl, 0) + 1

    report = {
        "flow_file": flow_path.name,
        "label_files": [Path(p).name for p in (label_csv_paths if isinstance(label_csv_paths, list) else [label_csv_paths])],
        "output_file": str(output_path),
        "flow_rows": n_flows,
        "label_csv_rows": label_rows,
        "matched": n_matched,
        "ambiguous": n_ambiguous,
        "unmatched": n_unmatched,
        "match_rate": n_matched / n_flows * 100 if n_flows else 0,
        "binary_label_counts": binary_counts,
        "ambiguous_key_count": len(ambiguous_keys),
    }
    return report
