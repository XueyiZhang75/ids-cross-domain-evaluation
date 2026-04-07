"""
io_utils.py — Reusable I/O helpers shared across all project modules.
"""

from pathlib import Path

import yaml


# ---------------------------------------------------------------------------
# Directory helpers
# ---------------------------------------------------------------------------

def ensure_dir(path: str | Path) -> Path:
    """Create *path* (and parents) if it does not exist. Return the Path."""
    p = Path(path)
    p.mkdir(parents=True, exist_ok=True)
    return p


# ---------------------------------------------------------------------------
# Config loading
# ---------------------------------------------------------------------------

def load_yaml(path: str | Path) -> dict:
    """Load a YAML file and return its contents as a dict."""
    path = Path(path)
    if not path.is_file():
        raise FileNotFoundError(f"Config file not found: {path}")
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


# ---------------------------------------------------------------------------
# Data export — thin wrappers so the rest of the code never calls
# pandas I/O directly.  Keeps format choices in one place.
# ---------------------------------------------------------------------------

def save_csv(df, path: str | Path, **kwargs) -> Path:
    """Write a DataFrame to CSV. Returns the output path."""
    path = Path(path)
    ensure_dir(path.parent)
    df.to_csv(path, index=False, **kwargs)
    return path


def save_parquet(df, path: str | Path, **kwargs) -> Path:
    """Write a DataFrame to Parquet. Returns the output path."""
    path = Path(path)
    ensure_dir(path.parent)
    df.to_parquet(path, index=False, **kwargs)
    return path
