"""Normalize raw inventory data — SKUs, quantities, dates, and whitespace."""

import math
import re
import unicodedata
from datetime import datetime

import pandas as pd

from .config import DEFAULT_CONFIG
from .models import QualityIssue

SKU_PATTERN = re.compile(r"^SKU-?(\d+)$", re.IGNORECASE)


def normalize_text(raw, unicode_form: str = "NFKC") -> str:
    """Normalize text using Unicode normalization and stripping whitespace."""
    if raw is None or (isinstance(raw, float) and math.isnan(raw)):
        return ""
    cleaned = str(raw).strip()
    return unicodedata.normalize(unicode_form, cleaned)


def normalize_sku(raw, config: dict | None = None) -> str:
    """Normalize a SKU to the canonical format SKU-NNN.

    Handles: missing hyphens (SKU005), lowercase (sku-008), extra whitespace,
    Unicode variations, and None/NaN values (returns empty string).
    """
    cfg = config or DEFAULT_CONFIG["sku"]
    pattern = re.compile(cfg.get("pattern", r"^SKU-?(\d+)$"), re.IGNORECASE)
    case = cfg.get("case", "upper")

    cleaned = normalize_text(raw)
    if not cleaned:
        return ""
    match = pattern.match(cleaned)
    if match:
        digits = match.group(1)
        fmt = cfg.get("format", "SKU-{:03d}")
        return fmt.format(int(digits))
    return cleaned.upper() if case == "upper" else cleaned


def normalize_quantity(raw: str, config: dict | None = None) -> int | None:
    """Convert a quantity string to an integer.

    Converts integer-valued floats (e.g., "70.0") to int.
    Rejects genuine fractional values (e.g., "70.5") — returns None.
    Returns None if the value cannot be parsed.
    """
    cfg = config or DEFAULT_CONFIG["quantity"]
    try:
        val = float(str(raw).strip())
        int_val = int(val)
        if val != int_val:
            if cfg.get("allow_fractional", False):
                return int_val  # Truncate if allowed
            return None  # Genuine fraction — reject
        return int_val
    except (ValueError, TypeError, AttributeError):
        return None


def normalize_date(raw, config: dict | None = None) -> str | None:
    """Normalize a date string to the configured output format.

    Handles:
        - ISO format: 2024-01-15
        - US format: 01/15/2024
        - None/NaN: returns None
    """
    cfg = config or DEFAULT_CONFIG["date"]
    if raw is None or (isinstance(raw, float) and math.isnan(raw)):
        return None
    raw_str = str(raw).strip()
    if not raw_str:
        return None
    output_fmt = cfg.get("output_format", "%Y-%m-%d")
    for fmt in cfg.get("formats", ["%Y-%m-%d", "%m/%d/%Y"]):
        try:
            return datetime.strptime(raw_str, fmt).strftime(output_fmt)
        except ValueError:
            continue
    return None


def normalize_dataframe(
    df: pd.DataFrame, snapshot_label: str, config: dict | None = None,
) -> tuple[pd.DataFrame, list[QualityIssue]]:
    """Normalize all fields in a snapshot DataFrame.

    Args:
        df: DataFrame with columns: sku, name, quantity, location, date.
        snapshot_label: Label for issue reporting (e.g., "snapshot_1").
        config: Optional normalization config dict. Uses defaults if None.

    Returns:
        Tuple of (normalized DataFrame, list of quality issues found).
    """
    cfg = config or DEFAULT_CONFIG
    df = df.copy()
    issues: list[QualityIssue] = []

    # --- SKU normalization ---
    raw_skus = df["sku"].copy()
    df["sku"] = df["sku"].apply(lambda x: normalize_sku(x, cfg.get("sku")))
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
    name_cfg = cfg.get("name", {})
    unicode_form = name_cfg.get("unicode_normalize", "NFKC")
    raw_names = df["name"].copy()
    df["name"] = df["name"].apply(lambda x: normalize_text(x, unicode_form))
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
    qty_cfg = cfg.get("quantity", {})
    raw_quantities = df["quantity"].copy()
    df["quantity"] = df["quantity"].apply(lambda x: normalize_quantity(x, qty_cfg))
    for sku, raw, normalized in zip(df["sku"], raw_quantities, df["quantity"]):
        raw_str = str(raw).strip()
        if normalized is None and raw_str:
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
    loc_cfg = cfg.get("location", {})
    loc_unicode = loc_cfg.get("unicode_normalize", "NFKC")
    use_title = loc_cfg.get("title_case", True)
    raw_locations = df["location"].copy()
    if use_title:
        df["location"] = df["location"].apply(
            lambda x: normalize_text(x, loc_unicode).title()
        )
    else:
        df["location"] = df["location"].apply(lambda x: normalize_text(x, loc_unicode))

    for sku, raw, cleaned in zip(df["sku"], raw_locations, df["location"]):
        if raw != cleaned:
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
    date_cfg = cfg.get("date", {})
    raw_dates = df["date"].copy()
    df["date"] = df["date"].apply(lambda x: normalize_date(x, date_cfg))
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
