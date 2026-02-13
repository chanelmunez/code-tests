"""Core reconciliation logic — compare two inventory snapshots."""

import pandas as pd

from .models import ItemChange, ReconciliationResult, QualityIssue
from .validator import get_duplicate_skus


def reconcile(
    df1: pd.DataFrame,
    df2: pd.DataFrame,
    quality_issues: list[QualityIssue] | None = None,
) -> ReconciliationResult:
    """Reconcile two normalized inventory snapshots.

    Matches items by SKU and classifies each as added, removed, changed, or unchanged.
    Duplicate SKUs (in either snapshot) are excluded from reconciliation and reported.

    Args:
        df1: Normalized snapshot_1 DataFrame.
        df2: Normalized snapshot_2 DataFrame.
        quality_issues: Pre-collected quality issues to include in the result.

    Returns:
        ReconciliationResult with categorized items and quality issues.
    """
    quality_issues = list(quality_issues) if quality_issues else []

    # Identify and exclude duplicate SKUs from both snapshots
    dupes_1 = get_duplicate_skus(df1)
    dupes_2 = get_duplicate_skus(df2)
    all_dupes = dupes_1 | dupes_2

    if all_dupes:
        df1 = df1[~df1["sku"].isin(all_dupes)].copy()
        df2 = df2[~df2["sku"].isin(all_dupes)].copy()

    skus_1 = set(df1["sku"])
    skus_2 = set(df2["sku"])

    removed_skus = skus_1 - skus_2
    added_skus = skus_2 - skus_1
    common_skus = skus_1 & skus_2

    # Index by SKU for efficient lookups
    snap1 = df1.set_index("sku")
    snap2 = df2.set_index("sku")

    added: list[ItemChange] = []
    removed: list[ItemChange] = []
    changed: list[ItemChange] = []
    unchanged: list[ItemChange] = []

    # Items only in snapshot_2 (newly added)
    for sku in sorted(added_skus):
        row = snap2.loc[sku]
        added.append(ItemChange(
            sku=sku,
            status="added",
            name=row["name"],
            new_quantity=int(row["quantity"]),
        ))

    # Items only in snapshot_1 (removed/sold out)
    for sku in sorted(removed_skus):
        row = snap1.loc[sku]
        removed.append(ItemChange(
            sku=sku,
            status="removed",
            name=row["name"],
            old_quantity=int(row["quantity"]),
        ))

    # Items in both — check for changes
    for sku in sorted(common_skus):
        row1 = snap1.loc[sku]
        row2 = snap2.loc[sku]

        qty1 = int(row1["quantity"])
        qty2 = int(row2["quantity"])
        name1 = row1["name"]
        name2 = row2["name"]
        loc1 = row1["location"]
        loc2 = row2["location"]

        qty_changed = qty1 != qty2
        name_diff = name1 != name2
        loc_diff = loc1 != loc2

        if qty_changed or name_diff or loc_diff:
            changed.append(ItemChange(
                sku=sku,
                status="changed",
                name=name2,  # Use the latest name
                old_quantity=qty1,
                new_quantity=qty2,
                quantity_delta=qty2 - qty1,
                old_name=name1 if name_diff else None,
                new_name=name2 if name_diff else None,
                name_changed=name_diff,
                old_location=loc1 if loc_diff else None,
                new_location=loc2 if loc_diff else None,
                location_changed=loc_diff,
            ))
        else:
            unchanged.append(ItemChange(
                sku=sku,
                status="unchanged",
                name=name1,
                old_quantity=qty1,
                new_quantity=qty2,
                quantity_delta=0,
            ))

    return ReconciliationResult(
        added=added,
        removed=removed,
        changed=changed,
        unchanged=unchanged,
        quality_issues=quality_issues,
        skipped_skus=sorted(all_dupes),
    )
