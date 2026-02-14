"""Core reconciliation logic — compare two inventory snapshots."""

import pandas as pd
from rapidfuzz import fuzz

from .models import ItemChange, ReconciliationResult, QualityIssue
from .validator import get_duplicate_skus


def _safe_int(value: object) -> int | None:
    """Convert a value to int, returning None if it can't be parsed."""
    if value is None:
        return None
    try:
        return int(value)
    except (ValueError, TypeError):
        return None


def _build_key(df: pd.DataFrame, key_mode: str) -> pd.Series:
    """Build the reconciliation key column from the DataFrame."""
    if key_mode == "sku_location":
        return df["sku"] + "|" + df["location"]
    return df["sku"]


def _get_duplicate_keys(df: pd.DataFrame, key_mode: str) -> set[str]:
    """Return the set of keys that appear more than once."""
    keys = _build_key(df, key_mode)
    counts = keys.value_counts()
    return set(counts[counts > 1].index)


def _within_tolerance(
    delta: int, old_qty: int, tolerance: int = 0, tolerance_pct: float = 0.0,
) -> bool:
    """Check whether a quantity delta falls within the configured tolerance."""
    if tolerance > 0 and abs(delta) <= tolerance:
        return True
    if tolerance_pct > 0 and old_qty != 0:
        pct_change = abs(delta) / abs(old_qty) * 100
        if pct_change <= tolerance_pct:
            return True
    return False


def _assign_priority(delta: int, old_qty: int, name_changed: bool) -> str:
    """Assign a priority level based on the magnitude of change.

    - high: name change, or >10% quantity variance
    - medium: 5-10% quantity variance
    - low: <5% quantity variance
    """
    if name_changed:
        return "high"
    if old_qty == 0:
        return "high" if delta != 0 else "low"
    pct = abs(delta) / abs(old_qty) * 100
    if pct > 10:
        return "high"
    if pct >= 5:
        return "medium"
    return "low"


def reconcile(
    df1: pd.DataFrame,
    df2: pd.DataFrame,
    quality_issues: list[QualityIssue] | None = None,
    key_mode: str = "sku",
    tolerance: int = 0,
    tolerance_pct: float = 0.0,
) -> ReconciliationResult:
    """Reconcile two normalized inventory snapshots.

    Matches items by key and classifies each as added, removed, changed, or unchanged.

    Args:
        df1: Normalized snapshot_1 DataFrame.
        df2: Normalized snapshot_2 DataFrame.
        quality_issues: Pre-collected quality issues to include in the result.
        key_mode: "sku" (default) to match by SKU alone, or "sku_location"
            to match by (SKU, location) composite key.
        tolerance: Absolute tolerance — deltas <= this value are "within_tolerance".
        tolerance_pct: Percentage tolerance — deltas <= this % of old quantity are tolerated.

    Returns:
        ReconciliationResult with categorized items and quality issues.
    """
    quality_issues = list(quality_issues) if quality_issues else []

    # Identify keys to exclude: duplicates + any with error-level issues
    if key_mode == "sku":
        dupes_1 = get_duplicate_skus(df1)
        dupes_2 = get_duplicate_skus(df2)
    else:
        dupes_1 = _get_duplicate_keys(df1, key_mode)
        dupes_2 = _get_duplicate_keys(df2, key_mode)

    error_skus = {
        issue.sku for issue in quality_issues
        if issue.severity == "error"
    }
    skipped = dupes_1 | dupes_2

    # Build keys for each row
    df1 = df1.copy()
    df2 = df2.copy()
    df1["_key"] = _build_key(df1, key_mode)
    df2["_key"] = _build_key(df2, key_mode)

    # Exclude error SKUs (always by raw SKU, since errors are per-SKU)
    if error_skus:
        df1 = df1[~df1["sku"].isin(error_skus)]
        df2 = df2[~df2["sku"].isin(error_skus)]
        skipped = skipped | error_skus

    if skipped:
        df1 = df1[~df1["_key"].isin(skipped)].copy()
        df2 = df2[~df2["_key"].isin(skipped)].copy()

    keys_1 = set(df1["_key"])
    keys_2 = set(df2["_key"])

    removed_keys = keys_1 - keys_2
    added_keys = keys_2 - keys_1
    common_keys = keys_1 & keys_2

    # Index by key for efficient lookups
    snap1 = df1.set_index("_key")
    snap2 = df2.set_index("_key")

    added: list[ItemChange] = []
    removed: list[ItemChange] = []
    changed: list[ItemChange] = []
    unchanged: list[ItemChange] = []
    tolerated: list[ItemChange] = []

    # Items only in snapshot_2 (newly added)
    for key in sorted(added_keys):
        row = snap2.loc[key]
        qty = _safe_int(row["quantity"])
        if qty is None:
            continue
        added.append(ItemChange(
            sku=row["sku"],
            status="added",
            name=row["name"],
            location=row["location"],
            new_quantity=qty,
        ))

    # Items only in snapshot_1 (removed/sold out)
    for key in sorted(removed_keys):
        row = snap1.loc[key]
        qty = _safe_int(row["quantity"])
        if qty is None:
            continue
        removed.append(ItemChange(
            sku=row["sku"],
            status="removed",
            name=row["name"],
            location=row["location"],
            old_quantity=qty,
        ))

    # Items in both — check for changes
    for key in sorted(common_keys):
        row1 = snap1.loc[key]
        row2 = snap2.loc[key]

        qty1 = _safe_int(row1["quantity"])
        qty2 = _safe_int(row2["quantity"])
        if qty1 is None or qty2 is None:
            continue
        delta = qty2 - qty1
        name1 = row1["name"]
        name2 = row2["name"]
        loc1 = row1["location"]
        loc2 = row2["location"]

        qty_changed = qty1 != qty2
        name_diff = name1 != name2
        loc_diff = loc1 != loc2

        if qty_changed or name_diff or loc_diff:
            # Check if the only change is a quantity delta within tolerance
            only_qty = qty_changed and not name_diff and not loc_diff
            if only_qty and _within_tolerance(delta, qty1, tolerance, tolerance_pct):
                tolerated.append(ItemChange(
                    sku=row2["sku"],
                    status="within_tolerance",
                    name=name2,
                    location=loc2,
                    old_quantity=qty1,
                    new_quantity=qty2,
                    quantity_delta=delta,
                ))
            else:
                similarity = None
                if name_diff:
                    similarity = round(fuzz.ratio(name1, name2) / 100.0, 3)
                priority = _assign_priority(delta, qty1, name_diff)
                changed.append(ItemChange(
                    sku=row2["sku"],
                    status="changed",
                    name=name2,
                    location=loc2,
                    old_quantity=qty1,
                    new_quantity=qty2,
                    quantity_delta=delta,
                    old_name=name1 if name_diff else None,
                    new_name=name2 if name_diff else None,
                    name_changed=name_diff,
                    old_location=loc1 if loc_diff else None,
                    new_location=loc2 if loc_diff else None,
                    location_changed=loc_diff,
                    name_similarity=similarity,
                    priority=priority,
                ))
        else:
            unchanged.append(ItemChange(
                sku=row1["sku"],
                status="unchanged",
                name=name1,
                location=loc1,
                old_quantity=qty1,
                new_quantity=qty2,
                quantity_delta=0,
            ))

    return ReconciliationResult(
        added=added,
        removed=removed,
        changed=changed,
        unchanged=unchanged,
        within_tolerance=tolerated,
        quality_issues=quality_issues,
        skipped_skus=sorted(skipped),
    )
