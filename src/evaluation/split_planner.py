"""
split_planner.py — Plan and audit train/val/test splits for CIC-IDS2017.

Reads feature parquets (or labeled flow parquets) and produces a split
summary based on capture-day assignment.
"""

from pathlib import Path

import pandas as pd

from src.utils.logging_utils import get_logger

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Day detection
# ---------------------------------------------------------------------------

def detect_day(pcap_file: str) -> str:
    """Extract the capture day from a pcap_file string."""
    lower = pcap_file.lower()
    for day in ["monday", "tuesday", "wednesday", "thursday", "friday"]:
        if day in lower:
            return day.capitalize()
    return "Unknown"


# ---------------------------------------------------------------------------
# Split planning
# ---------------------------------------------------------------------------

# Default CIC-IDS2017 split assignment.
# Rationale documented in the function below.
DEFAULT_SPLIT_ASSIGNMENT = {
    "Monday":    "train",
    "Tuesday":   "train",
    "Wednesday": "train",
    "Thursday":  "val",
    "Friday":    "test",
}


def plan_split(
    feature_paths: list[str | Path],
    split_assignment: dict[str, str] | None = None,
) -> dict:
    """Load feature parquets and produce a split summary.

    Parameters
    ----------
    feature_paths : list of paths
        Feature parquet files to include.
    split_assignment : dict, optional
        Mapping from day name to split role ("train", "val", "test").
        Defaults to DEFAULT_SPLIT_ASSIGNMENT.

    Returns
    -------
    dict with per-day stats and per-split aggregates.
    """
    if split_assignment is None:
        split_assignment = DEFAULT_SPLIT_ASSIGNMENT

    # Load and tag by day.
    frames = []
    for p in feature_paths:
        df = pd.read_parquet(p)
        frames.append(df)
    combined = pd.concat(frames, ignore_index=True)

    # Filter to clean labeled rows.
    clean_mask = (
        (combined["matched_flag"] == True) &
        (combined["ambiguous_flag"] == False) &
        (combined["binary_label"].isin(["benign", "attack"]))
    )
    clean = combined[clean_mask].copy()
    clean["day"] = clean["pcap_file"].apply(detect_day)

    # Per-day stats.
    day_stats = []
    for day in sorted(clean["day"].unique()):
        ddf = clean[clean["day"] == day]
        bl = ddf["binary_label"].value_counts()
        benign = int(bl.get("benign", 0))
        attack = int(bl.get("attack", 0))
        total = benign + attack
        role = split_assignment.get(day, "unassigned")

        # Attack type breakdown.
        attack_types = {}
        if attack > 0:
            atk = ddf[ddf["binary_label"] == "attack"]
            attack_types = atk["original_label"].value_counts().to_dict()

        day_stats.append({
            "day": day,
            "split": role,
            "total": total,
            "benign": benign,
            "attack": attack,
            "attack_pct": attack / total * 100 if total else 0,
            "attack_types": attack_types,
        })

    # Per-split aggregates.
    split_agg = {}
    for role in ["train", "val", "test", "unassigned"]:
        days_in_role = [d for d in day_stats if d["split"] == role]
        if days_in_role:
            split_agg[role] = {
                "days": [d["day"] for d in days_in_role],
                "total": sum(d["total"] for d in days_in_role),
                "benign": sum(d["benign"] for d in days_in_role),
                "attack": sum(d["attack"] for d in days_in_role),
            }

    return {
        "total_clean_rows": len(clean),
        "total_raw_rows": len(combined),
        "dropped": len(combined) - len(clean),
        "split_assignment": split_assignment,
        "day_stats": day_stats,
        "split_aggregates": split_agg,
    }
