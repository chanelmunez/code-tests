"""Normalize raw inventory data — SKUs, quantities, dates, and whitespace."""

import re
from datetime import datetime

import pandas as pd

from .models import QualityIssue

SKU_PATTERN = re.compile(r"^SKU-?(\d+)$", re.IGNORECASE)


def normalize_sku(raw: str) -> str:
    """Normalize a SKU to the canonical format SKU-NNN.

    Handles: missing hyphens (SKU005), lowercase (sku-008), extra whitespace.
    """
    cleaned = raw.strip()
    match = SKU_PATTERN.match(cleaned)
    if match:
        digits = match.group(1).zfill(3)
        return f"SKU-{digits}"
    # If it doesn't match the expected pattern, return stripped uppercase
    return cleaned.upper()


def normalize_quantity(raw: str) -> int | None:
    """Convert a quantity string to an integer.

    Handles float-like strings (e.g., "70.0", "80.00") by truncating to int.
    Returns None if the value cannot be parsed.
    """
    try:
        return int(float(raw.strip()))
    except (ValueError, TypeError, AttributeError):
        return None


def normalize_date(raw: str) -> str | None:
    """Normalize a date string to ISO format (YYYY-MM-DD).

    Handles:
        - ISO format: 2024-01-15
        - US format: 01/15/2024
    """
    raw = raw.strip()
    for fmt in ("%Y-%m-%d", "%m/%d/%Y"):
        try:
            return datetime.strptime(raw, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return None


def normalize_dataframe(
    df: pd.DataFrame, snapshot_label: str
) -> tuple[pd.DataFrame, list[QualityIssue]]:
    """Normalize all fields in a snapshot DataFrame.

    Args:
        df: DataFrame with columns: sku, name, quantity, location, date.
        snapshot_label: Label for issue reporting (e.g., "snapshot_1").

    Returns:
        Tuple of (normalized DataFrame, list of quality issues found).
    """
    df = df.copy()
    issues: list[QualityIssue] = []

    # --- SKU normalization ---
    raw_skus = df["sku"].copy()
    df["sku"] = df["sku"].apply(normalize_sku)
    for idx, (raw, normalized) in enumerate(zip(raw_skus, df["sku"])):
        if raw != normalized:
            issues.append(QualityIssue(
                sku=normalized,
                field="sku",
                issue_type="sku_format",
                detail=f"SKU format inconsistency: '{raw}' normalized to '{normalized}'",
                snapshot=snapshot_label,
                original_value=raw,
                corrected_value=normalized,
            ))

    # --- Name normalization (strip whitespace) ---
    raw_names = df["name"].copy()
    df["name"] = df["name"].str.strip()
    for idx, (sku, raw, cleaned) in enumerate(zip(df["sku"], raw_names, df["name"])):
        if raw != cleaned:
            issues.append(QualityIssue(
                sku=sku,
                field="name",
                issue_type="whitespace",
                detail=f"Whitespace in product name: '{raw}' → '{cleaned}'",
                snapshot=snapshot_label,
                original_value=raw,
                corrected_value=cleaned,
            ))

    # --- Quantity normalization ---
    raw_quantities = df["quantity"].copy()
    df["quantity"] = df["quantity"].apply(normalize_quantity)
    for idx, (sku, raw, normalized) in enumerate(zip(df["sku"], raw_quantities, df["quantity"])):
        raw_str = str(raw).strip()
        if normalized is not None and "." in raw_str:
            issues.append(QualityIssue(
                sku=sku,
                field="quantity",
                issue_type="float_quantity",
                detail=f"Quantity stored as float: '{raw_str}' → {normalized}",
                snapshot=snapshot_label,
                original_value=raw_str,
                corrected_value=str(normalized),
            ))

    # --- Location normalization (strip whitespace) ---
    df["location"] = df["location"].str.strip()

    # --- Date normalization ---
    raw_dates = df["date"].copy()
    df["date"] = df["date"].apply(normalize_date)
    for idx, (sku, raw, normalized) in enumerate(zip(df["sku"], raw_dates, df["date"])):
        raw_str = str(raw).strip()
        if normalized and raw_str != normalized:
            issues.append(QualityIssue(
                sku=sku,
                field="date",
                issue_type="date_format",
                detail=f"Non-standard date format: '{raw_str}' → '{normalized}'",
                snapshot=snapshot_label,
                original_value=raw_str,
                corrected_value=normalized,
            ))

    return df, issues
