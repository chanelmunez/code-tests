"""Generate reconciliation reports in JSON and CSV formats."""

import csv
import json
from datetime import datetime
from pathlib import Path

from .models import ReconciliationResult


def generate_json_report(
    result: ReconciliationResult,
    output_path: str | Path,
    snapshot_1_path: str = "",
    snapshot_2_path: str = "",
) -> None:
    """Write a full structured reconciliation report as JSON.

    The report includes metadata, summary statistics, categorized items,
    and all data quality issues found.
    """
    report = {
        "metadata": {
            "generated_at": datetime.now().isoformat(),
            "snapshot_1": str(snapshot_1_path),
            "snapshot_2": str(snapshot_2_path),
        },
        "summary": result.summary,
        "reconciliation": {
            "added": [item.to_dict() for item in result.added],
            "removed": [item.to_dict() for item in result.removed],
            "changed": [item.to_dict() for item in result.changed],
            "unchanged": [item.to_dict() for item in result.unchanged],
        },
        "skipped_skus": result.skipped_skus,
        "quality_issues": [issue.to_dict() for issue in result.quality_issues],
    }

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, indent=2) + "\n")


def generate_csv_report(
    result: ReconciliationResult, output_path: str | Path
) -> None:
    """Write a flat reconciliation summary as CSV.

    Each row represents one SKU with its reconciliation status and changes.
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    fieldnames = [
        "sku",
        "status",
        "name",
        "old_quantity",
        "new_quantity",
        "quantity_delta",
        "name_changed",
        "old_name",
        "new_name",
        "location_changed",
        "old_location",
        "new_location",
    ]

    with open(output_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for item in result.all_items:
            writer.writerow(item.to_flat_dict())
