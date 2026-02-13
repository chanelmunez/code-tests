"""Normalize raw inventory data — SKUs, quantities, dates, and whitespace."""

import math
import re
import unicodedata
from datetime import datetime

import pandas as pd

from .models import QualityIssue

SKU_PATTERN = re.compile(r"^SKU-?(\d+)$", re.IGNORECASE)


def normalize_text(raw) -> str:
    """Normalize text using NFKC normalization and stripping whitespace.

    Handles Unicode equivalence (e.g., composed vs decomposed accents)
    and removes surrounding whitespace.
    """
    if raw is None or (isinstance(raw, float) and math.isnan(raw)):
        return ""
    cleaned = str(raw).strip()
    return unicodedata.normalize("NFKC", cleaned)


def normalize_sku(raw) -> str:
    """Normalize a SKU to the canonical format SKU-NNN.

    Handles: missing hyphens (SKU005), lowercase (sku-008), extra whitespace,
    Unicode variations, and None/NaN values (returns empty string).
    """
    cleaned = normalize_text(raw)
    if not cleaned:
        return ""
    match = SKU_PATTERN.match(cleaned)
    if match:
        digits = match.group(1).zfill(3)
        return f"SKU-{digits}"
    # If it doesn't match the expected pattern, return stripped uppercase
    return cleaned.upper()


def normalize_quantity(raw: str) -> int | None:
    """Convert a quantity string to an integer.

    Converts integer-valued floats (e.g., "70.0") to int.
    Rejects genuine fractional values (e.g., "70.5") — returns None.
    Returns None if the value cannot be parsed.
    """
    try:
        val = float(str(raw).strip())
        int_val = int(val)
        if val != int_val:
            return None  # Genuine fraction — reject
        return int_val
    except (ValueError, TypeError, AttributeError):
        return None


def normalize_date(raw) -> str | None:
    """Normalize a date string to ISO format (YYYY-MM-DD).

    Handles:
        - ISO format: 2024-01-15
        - US format: 01/15/2024
        - None/NaN: returns None
    """
    if raw is None or (isinstance(raw, float) and math.isnan(raw)):
        return None
    raw_str = str(raw).strip()
    if not raw_str:
        return None
    for fmt in ("%Y-%m-%d", "%m/%d/%Y"):
        try:
            return datetime.strptime(raw_str, fmt).strftime("%Y-%m-%d")
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
    for raw, normalized in zip(raw_skus, df["sku"]):
        # Simple string comparison might fail if raw was None/float
        raw_str = str(raw) if raw is not None else ""
        if raw_str != normalized and not (raw_str == "nan" and normalized == ""):
             # We only want to flag if it was a meaningful change, not just nan->""
             # But the previous logic was simpler. Let's stick to what we had but be careful.
             pass
    
    # Re-implement the loop with cleaner logic
    for raw, normalized in zip(raw_skus, df["sku"]):
        # normalize_sku returns "" for None/NaN. 
        # We generally report issues if the content changed significantly.
        pass
    
    # Actually, let's keep the original reporting logic structure but use the new normalized values
    # The original loop:
    for raw, normalized in zip(raw_skus, df["sku"]):
        if raw != normalized:
            issues.append(QualityIssue(
                sku=normalized,
                field="sku",
                issue_type="sku_format",
                detail=f"SKU format inconsistency: '{raw}' normalized to '{normalized}'",
                snapshot=snapshot_label,
                original_value=str(raw),
                corrected_value=normalized,
            ))

    # --- Name normalization (Unicode + whitespace) ---
    raw_names = df["name"].copy()
    df["name"] = df["name"].apply(normalize_text)
    for sku, raw, cleaned in zip(df["sku"], raw_names, df["name"]):
        if raw != cleaned:
            issues.append(QualityIssue(
                sku=sku,
                field="name",
                issue_type="name_normalization",
                detail=f"Name normalized: '{raw}' → '{cleaned}'",
                snapshot=snapshot_label,
                original_value=str(raw),
                corrected_value=str(cleaned),
            ))

    # --- Quantity normalization ---
    raw_quantities = df["quantity"].copy()
    df["quantity"] = df["quantity"].apply(normalize_quantity)
    for sku, raw, normalized in zip(df["sku"], raw_quantities, df["quantity"]):
        raw_str = str(raw).strip()
        if normalized is None and raw_str:
            # Determine whether it's a fraction or completely unparseable
            try:
                float_val = float(raw_str)
                if float_val != int(float_val):
                    issues.append(QualityIssue(
                        sku=sku,
                        field="quantity",
                        issue_type="fractional_quantity",
                        detail=f"Fractional quantity not allowed: '{raw_str}'",
                        snapshot=snapshot_label,
                        original_value=raw_str,
                        severity="error",
                    ))
            except (ValueError, TypeError):
                issues.append(QualityIssue(
                    sku=sku,
                    field="quantity",
                    issue_type="invalid_quantity",
                    detail=f"Cannot parse quantity: '{raw_str}'",
                    snapshot=snapshot_label,
                    original_value=raw_str,
                    severity="error",
                ))
        elif normalized is not None and "." in raw_str:
            # Integer stored as float (70.0 → 70) — cosmetic, not an error
            issues.append(QualityIssue(
                sku=sku,
                field="quantity",
                issue_type="float_quantity",
                detail=f"Quantity stored as float: '{raw_str}' → {normalized}",
                snapshot=snapshot_label,
                original_value=raw_str,
                corrected_value=str(normalized),
            ))

    # --- Location normalization (Unicode + Title Case) ---
    raw_locations = df["location"].copy()
    # Normalize unicode then Title Case
    df["location"] = df["location"].apply(lambda x: normalize_text(x).title())
    
    for sku, raw, cleaned in zip(df["sku"], raw_locations, df["location"]):
        if raw != cleaned:
            # We don't always need to report this as a "QualityIssue" if it's just casing,
            # but it helps to be transparent.
             issues.append(QualityIssue(
                sku=sku,
                field="location",
                issue_type="location_normalization",
                detail=f"Location normalized: '{raw}' → '{cleaned}'",
                snapshot=snapshot_label,
                original_value=str(raw),
                corrected_value=cleaned,
            ))

    # --- Date normalization ---
    raw_dates = df["date"].copy()
    df["date"] = df["date"].apply(normalize_date)
    for sku, raw, normalized in zip(df["sku"], raw_dates, df["date"]):
        raw_str = str(raw).strip()
        if normalized is None and raw_str:
            issues.append(QualityIssue(
                sku=sku,
                field="date",
                issue_type="invalid_date",
                detail=f"Cannot parse date: '{raw_str}'",
                snapshot=snapshot_label,
                original_value=raw_str,
                severity="error",
            ))
        elif normalized and raw_str != normalized:
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
