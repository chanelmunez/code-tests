"""Load CSV snapshots and normalize column names to a standard schema."""

from pathlib import Path

import pandas as pd

# Maps variant column names to the standard schema.
# Standard columns: sku, name, quantity, location, date
COLUMN_ALIASES: dict[str, str] = {
    "product_name": "name",
    "qty": "quantity",
    "warehouse": "location",
    "last_counted": "date",
    "updated_at": "date",
}


def load_snapshot(path: str | Path) -> pd.DataFrame:
    """Load a CSV inventory snapshot and normalize column names.

    Args:
        path: Path to the CSV file.

    Returns:
        DataFrame with standardized column names: sku, name, quantity, location, date.

    Raises:
        FileNotFoundError: If the CSV file does not exist.
        ValueError: If required columns are missing after normalization.
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Snapshot file not found: {path}")

    df = pd.read_csv(path, dtype=str)  # Read everything as string initially

    # Normalize column names: strip whitespace and lowercase
    df.columns = df.columns.str.strip().str.lower()

    # Apply column aliases
    df = df.rename(columns=COLUMN_ALIASES)

    required_columns = {"sku", "name", "quantity", "location", "date"}
    missing = required_columns - set(df.columns)
    if missing:
        raise ValueError(
            f"Missing required columns after normalization: {missing}. "
            f"Available columns: {list(df.columns)}"
        )

    # Keep only standard columns in fixed order
    ordered_columns = ["sku", "name", "quantity", "location", "date"]
    df = df[ordered_columns]

    return df
