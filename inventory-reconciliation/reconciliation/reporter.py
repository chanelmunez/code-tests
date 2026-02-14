"""Generate reconciliation reports in JSON and CSV formats."""

import csv
import json
from datetime import datetime
from pathlib import Path

from .models import ItemChange, ReconciliationResult

SORT_KEYS = {
    "sku": lambda item: item.sku,
    "status": lambda item: item.status,
    "delta": lambda item: abs(item.quantity_delta or 0),
    "priority": lambda item: {"high": 0, "medium": 1, "low": 2, None: 3}.get(item.priority, 3),
}


def apply_filters(
    items: list[ItemChange],
    sort_by: str | None = None,
    filter_status: str | None = None,
) -> list[ItemChange]:
    """Apply optional sorting and filtering to reconciliation items."""
    if filter_status:
        items = [i for i in items if i.status == filter_status]
    if sort_by and sort_by in SORT_KEYS:
        reverse = sort_by == "delta"  # largest delta first
        items = sorted(items, key=SORT_KEYS[sort_by], reverse=reverse)
    return items


def generate_json_report(
    result: ReconciliationResult,
    output_path: str | Path,
    snapshot_1_path: str = "",
    snapshot_2_path: str = "",
    run_id: str | None = None,
) -> None:
    """Write a full structured reconciliation report as JSON."""
    effective_run_id = run_id or result.run_id
    metadata = {
        "generated_at": datetime.now().isoformat(),
        "snapshot_1": str(snapshot_1_path),
        "snapshot_2": str(snapshot_2_path),
    }
    if effective_run_id:
        metadata["run_id"] = effective_run_id

    report = {
        "metadata": metadata,
        "summary": result.summary,
        "health": result.health,
        "reconciliation": {
            "added": [item.to_dict() for item in result.added],
            "removed": [item.to_dict() for item in result.removed],
            "changed": [item.to_dict() for item in result.changed],
            "unchanged": [item.to_dict() for item in result.unchanged],
            "within_tolerance": [item.to_dict() for item in result.within_tolerance],
        },
        "skipped_skus": result.skipped_skus,
        "quality_issues": [issue.to_dict() for issue in result.quality_issues],
        "pipeline_log": result.pipeline_log,
    }

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, indent=2) + "\n")


def generate_csv_report(
    result: ReconciliationResult,
    output_path: str | Path,
    sort_by: str | None = None,
    filter_status: str | None = None,
) -> None:
    """Write a flat reconciliation summary as CSV.

    Args:
        result: The reconciliation result to write.
        output_path: Path for the output CSV file.
        sort_by: Optional sort key: "sku", "status", "delta", or "priority".
        filter_status: Optional status filter (e.g., "changed", "added").
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    fieldnames = [
        "sku",
        "status",
        "name",
        "location",
        "old_quantity",
        "new_quantity",
        "quantity_delta",
        "name_changed",
        "old_name",
        "new_name",
        "location_changed",
        "old_location",
        "new_location",
        "name_similarity",
        "priority",
    ]

    items = apply_filters(result.all_items, sort_by, filter_status)

    with open(output_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for item in items:
            writer.writerow(item.to_flat_dict())
