"""Data models for inventory reconciliation."""

from dataclasses import dataclass, field


@dataclass
class QualityIssue:
    """A data quality issue found during loading, normalization, or validation."""

    sku: str
    field: str
    issue_type: str
    detail: str
    snapshot: str
    original_value: str = ""
    corrected_value: str | None = None
    severity: str = "warning"  # "warning" or "error"

    def to_dict(self) -> dict:
        return {
            "sku": self.sku,
            "field": self.field,
            "issue_type": self.issue_type,
            "detail": self.detail,
            "snapshot": self.snapshot,
            "original_value": self.original_value,
            "corrected_value": self.corrected_value,
            "severity": self.severity,
        }


@dataclass
class ItemChange:
    """A single item's reconciliation result."""

    sku: str
    status: str  # "added", "removed", "changed", "unchanged", "within_tolerance"
    name: str
    location: str = ""  # Current location (always populated for variance-by-location)
    old_quantity: int | None = None
    new_quantity: int | None = None
    quantity_delta: int | None = None
    old_name: str | None = None
    new_name: str | None = None
    name_changed: bool = False
    old_location: str | None = None
    new_location: str | None = None
    location_changed: bool = False
    name_similarity: float | None = None
    priority: str | None = None  # "high", "medium", "low"

    def to_dict(self) -> dict:
        result = {
            "sku": self.sku,
            "status": self.status,
            "name": self.name,
        }
        if self.status in ("changed", "unchanged", "within_tolerance"):
            result["old_quantity"] = self.old_quantity
            result["new_quantity"] = self.new_quantity
            result["quantity_delta"] = self.quantity_delta
        elif self.status == "removed":
            result["last_quantity"] = self.old_quantity
        elif self.status == "added":
            result["quantity"] = self.new_quantity

        if self.name_changed:
            result["name_changed"] = True
            result["old_name"] = self.old_name
            result["new_name"] = self.new_name
            if self.name_similarity is not None:
                result["name_similarity"] = self.name_similarity
        if self.location_changed:
            result["location_changed"] = True
            result["old_location"] = self.old_location
            result["new_location"] = self.new_location

        if self.priority:
            result["priority"] = self.priority

        return result

    def to_flat_dict(self) -> dict:
        """Flat representation for CSV output."""
        return {
            "sku": self.sku,
            "status": self.status,
            "name": self.name,
            "location": self.location,
            "old_quantity": self.old_quantity,
            "new_quantity": self.new_quantity,
            "quantity_delta": self.quantity_delta,
            "name_changed": self.name_changed,
            "old_name": self.old_name,
            "new_name": self.new_name,
            "location_changed": self.location_changed,
            "old_location": self.old_location,
            "new_location": self.new_location,
            "name_similarity": self.name_similarity,
            "priority": self.priority,
        }


@dataclass
class ReconciliationResult:
    """Complete reconciliation output."""

    added: list[ItemChange] = field(default_factory=list)
    removed: list[ItemChange] = field(default_factory=list)
    changed: list[ItemChange] = field(default_factory=list)
    unchanged: list[ItemChange] = field(default_factory=list)
    within_tolerance: list[ItemChange] = field(default_factory=list)
    quality_issues: list[QualityIssue] = field(default_factory=list)
    skipped_skus: list[str] = field(default_factory=list)

    pipeline_log: list[dict] = field(default_factory=list)
    run_id: str = ""

    @property
    def summary(self) -> dict:
        snap1_count = (
            len(self.removed) + len(self.changed)
            + len(self.unchanged) + len(self.within_tolerance)
        )
        snap2_count = (
            len(self.added) + len(self.changed)
            + len(self.unchanged) + len(self.within_tolerance)
        )
        return {
            "total_snapshot_1": snap1_count,
            "total_snapshot_2": snap2_count,
            "added": len(self.added),
            "removed": len(self.removed),
            "changed": len(self.changed),
            "unchanged": len(self.unchanged),
            "within_tolerance": len(self.within_tolerance),
            "quality_issues": len(self.quality_issues),
            "skipped_due_to_errors": len(self.skipped_skus),
        }

    @property
    def health(self) -> dict:
        """Compute inventory health statistics."""
        # Accuracy = items that didn't change / total items in common
        common_count = (
            len(self.changed) + len(self.unchanged) + len(self.within_tolerance)
        )
        accurate = len(self.unchanged) + len(self.within_tolerance)
        accuracy_rate = round(accurate / common_count * 100, 1) if common_count > 0 else 100.0

        # Total absolute variance across all changed + tolerated items
        total_variance = sum(
            abs(item.quantity_delta or 0)
            for item in self.changed + self.within_tolerance
        )

        # Variance by location (from snapshot 2 perspective)
        variance_by_location: dict[str, int] = {}
        for item in self.changed + self.within_tolerance:
            loc = item.location or "Unknown"
            variance_by_location[loc] = (
                variance_by_location.get(loc, 0) + abs(item.quantity_delta or 0)
            )

        # Data quality score = rows that needed no normalization / total rows
        snap1_total = (
            len(self.removed) + len(self.changed)
            + len(self.unchanged) + len(self.within_tolerance)
        )
        snap2_total = (
            len(self.added) + len(self.changed)
            + len(self.unchanged) + len(self.within_tolerance)
        )
        total_rows = snap1_total + snap2_total
        issues_affecting_rows = len({
            i.sku for i in self.quality_issues
        })
        quality_score = round(
            (1 - issues_affecting_rows / total_rows) * 100, 1
        ) if total_rows > 0 else 100.0

        return {
            "accuracy_rate": accuracy_rate,
            "total_variance": total_variance,
            "variance_by_location": variance_by_location,
            "data_quality_score": quality_score,
        }

    @property
    def all_items(self) -> list[ItemChange]:
        return (
            self.added + self.removed + self.changed
            + self.unchanged + self.within_tolerance
        )
