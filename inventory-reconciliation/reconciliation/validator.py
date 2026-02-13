"""Validate inventory data for semantic issues after normalization."""

import pandas as pd

from .models import QualityIssue


def find_duplicate_skus(df: pd.DataFrame, snapshot_label: str) -> list[QualityIssue]:
    """Identify SKUs that appear more than once in a snapshot."""
    issues: list[QualityIssue] = []
    sku_counts = df["sku"].value_counts()
    duplicates = sku_counts[sku_counts > 1]

    for sku, count in duplicates.items():
        rows = df[df["sku"] == sku]
        row_details = "; ".join(
            f"name='{r['name']}', qty={r['quantity']}, loc='{r['location']}'"
            for _, r in rows.iterrows()
        )
        issues.append(QualityIssue(
            sku=str(sku),
            field="sku",
            issue_type="duplicate_sku",
            detail=f"SKU appears {count} times: [{row_details}]",
            snapshot=snapshot_label,
            original_value=str(sku),
            severity="error",
        ))

    return issues


def find_negative_quantities(df: pd.DataFrame, snapshot_label: str) -> list[QualityIssue]:
    """Flag rows where quantity is negative."""
    issues: list[QualityIssue] = []
    negatives = df[df["quantity"].notna() & (df["quantity"] < 0)]

    for _, row in negatives.iterrows():
        issues.append(QualityIssue(
            sku=row["sku"],
            field="quantity",
            issue_type="negative_quantity",
            detail=f"Negative quantity: {int(row['quantity'])}",
            snapshot=snapshot_label,
            original_value=str(int(row["quantity"])),
            severity="error",
        ))

    return issues


def find_null_fields(df: pd.DataFrame, snapshot_label: str) -> list[QualityIssue]:
    """Flag rows with null or empty required fields."""
    issues: list[QualityIssue] = []

    for col in ["sku", "name", "quantity", "location", "date"]:
        nulls = df[df[col].isna() | (df[col].astype(str).str.strip() == "")]
        for _, row in nulls.iterrows():
            issues.append(QualityIssue(
                sku=row.get("sku", "UNKNOWN"),
                field=col,
                issue_type="missing_value",
                detail=f"Missing or empty value for '{col}'",
                snapshot=snapshot_label,
                severity="error",
            ))

    return issues


def validate_snapshot(df: pd.DataFrame, snapshot_label: str) -> list[QualityIssue]:
    """Run all validation checks on a normalized snapshot.

    Returns:
        Combined list of all quality issues found.
    """
    issues: list[QualityIssue] = []
    issues.extend(find_duplicate_skus(df, snapshot_label))
    issues.extend(find_negative_quantities(df, snapshot_label))
    issues.extend(find_null_fields(df, snapshot_label))
    return issues


def get_duplicate_skus(df: pd.DataFrame) -> set[str]:
    """Return the set of SKUs that appear more than once."""
    sku_counts = df["sku"].value_counts()
    return set(sku_counts[sku_counts > 1].index)
