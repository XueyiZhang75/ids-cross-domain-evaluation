"""
label_ref_loader.py — Discover, read, and normalise label-reference CSVs.

This module handles the public CSV files that ship with IDS datasets.
These CSVs are used **only** as label references — never as training features.

Typical usage:

    from src.labeling.label_ref_loader import discover_csvs, load_label_ref

    csv_paths = discover_csvs("D:/ids_project_data/cicids2017/label_ref")
    for path in csv_paths:
        df, summary = load_label_ref(path)
"""

from pathlib import Path

import pandas as pd

from src.utils.logging_utils import get_logger

logger = get_logger(__name__)

# Common label column names across datasets (case-insensitive, stripped).
_LABEL_CANDIDATES = {"label", "attack_cat", "Label"}


# ---------------------------------------------------------------------------
# Discovery
# ---------------------------------------------------------------------------

def discover_csvs(label_ref_dir: str | Path) -> list[Path]:
    """Return sorted list of CSV files in *label_ref_dir*.

    Raises FileNotFoundError if the directory does not exist.
    Logs a warning if no CSVs are found.
    """
    d = Path(label_ref_dir)
    if not d.is_dir():
        raise FileNotFoundError(f"Label-reference directory not found: {d}")

    csvs = sorted(d.glob("*.csv"))
    if not csvs:
        logger.warning("No CSV files found in %s", d)
    else:
        logger.info("Found %d CSV file(s) in %s", len(csvs), d)
    return csvs


# ---------------------------------------------------------------------------
# Reading and normalisation
# ---------------------------------------------------------------------------

def _detect_label_column(columns: list[str]) -> str | None:
    """Find the label column among *columns* (already stripped)."""
    for col in columns:
        if col.lower() in {c.lower() for c in _LABEL_CANDIDATES}:
            return col
    return None


def load_label_ref(
    csv_path: str | Path,
    nrows: int | None = None,
) -> tuple[pd.DataFrame, dict]:
    """Read a label-reference CSV and return (dataframe, summary).

    Processing steps:
    1. Read the CSV (optionally limited to *nrows*).
    2. Strip leading/trailing whitespace from all column names.
    3. Detect the label column.
    4. Build a summary dict with basic metadata.

    Parameters
    ----------
    csv_path : path
        Path to a single CSV file.
    nrows : int, optional
        If given, read only the first *nrows* rows (useful for quick checks).

    Returns
    -------
    df : pd.DataFrame
        The dataframe with normalised column names.
    summary : dict
        Metadata: filename, shape, column list, label column name,
        and label value counts (top 10).
    """
    csv_path = Path(csv_path)
    if not csv_path.is_file():
        raise FileNotFoundError(f"CSV file not found: {csv_path}")

    logger.info("Reading %s%s", csv_path.name,
                f" (first {nrows} rows)" if nrows else "")

    # CIC-IDS2017 CSVs are mostly UTF-8 but some files contain Windows-1252
    # bytes (e.g., 0x96 en-dash). Try UTF-8 first, fall back to latin-1.
    for enc in ("utf-8", "latin-1"):
        try:
            df = pd.read_csv(csv_path, nrows=nrows, encoding=enc,
                             on_bad_lines="skip", low_memory=False)
            if enc != "utf-8":
                logger.info("  Fell back to encoding=%s for %s", enc, csv_path.name)
            break
        except UnicodeDecodeError:
            continue
    else:
        raise ValueError(f"Could not decode {csv_path.name} with utf-8 or latin-1")

    # Normalise column names: strip whitespace.
    df.columns = df.columns.str.strip()

    # Detect label column.
    label_col = _detect_label_column(df.columns.tolist())
    if label_col is None:
        logger.warning("No label column detected in %s", csv_path.name)

    # Label value counts (top 10).
    label_counts = {}
    if label_col is not None:
        vc = df[label_col].value_counts()
        label_counts = vc.head(10).to_dict()

    summary = {
        "filename": csv_path.name,
        "rows": len(df),
        "columns_count": len(df.columns),
        "columns": df.columns.tolist(),
        "label_column": label_col,
        "label_value_counts": label_counts,
    }
    return df, summary


# ---------------------------------------------------------------------------
# Batch summary
# ---------------------------------------------------------------------------

def summarise_label_refs(
    label_ref_dir: str | Path,
    nrows: int | None = None,
) -> list[dict]:
    """Discover and summarise all label-reference CSVs in a directory.

    Returns a list of summary dicts (one per CSV).
    """
    csv_paths = discover_csvs(label_ref_dir)
    summaries = []
    for p in csv_paths:
        _, summary = load_label_ref(p, nrows=nrows)
        summaries.append(summary)
    return summaries
