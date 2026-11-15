"""Read raw FIRMS archive CSVs.

Two readers are provided:

* ``read_raw_strings`` — every column as text. Used by inspection so that
  unexpected values (e.g. an unknown confidence code) are observed exactly
  as they appear in the file rather than being coerced away.
* ``read_typed`` — explicit analytical dtypes, used by the pipeline.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from config.settings import SOURCE_COLUMNS, SOURCE_DTYPES


class SchemaError(ValueError):
    """Raised when a CSV does not contain the expected FIRMS columns."""


def read_header(csv_path: Path) -> list[str]:
    """Return the header columns of a CSV without reading the body."""
    return list(pd.read_csv(csv_path, nrows=0).columns)


def validate_columns(columns: list[str]) -> None:
    """Ensure every required FIRMS source column is present."""
    missing = [c for c in SOURCE_COLUMNS if c not in columns]
    if missing:
        raise SchemaError(f"Missing required source columns: {missing}. Found: {columns}")


def read_raw_strings(csv_path: Path) -> pd.DataFrame:
    """Read all required columns as strings (no coercion)."""
    validate_columns(read_header(csv_path))
    return pd.read_csv(
        csv_path,
        usecols=list(SOURCE_COLUMNS),
        dtype="string",
        keep_default_na=True,
    )


def read_typed(csv_path: Path) -> pd.DataFrame:
    """Read required columns with explicit analytical dtypes."""
    validate_columns(read_header(csv_path))
    return pd.read_csv(csv_path, usecols=list(SOURCE_COLUMNS), dtype=SOURCE_DTYPES)
