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
    status: str  # "added", "removed", "changed", "unchanged"
    name: str
    old_quantity: int | None = None
    new_quantity: int | None = None
    quantity_delta: int | None = None
    old_name: str | None = None
    new_name: str | None = None
    name_changed: bool = False
    old_location: str | None = None
    new_location: str | None = None
    location_changed: bool = False

    def to_dict(self) -> dict:
        result = {
            "sku": self.sku,
            "status": self.status,
            "name": self.name,
        }
        if self.status in ("changed", "unchanged"):
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
        if self.location_changed:
            result["location_changed"] = True
            result["old_location"] = self.old_location
            result["new_location"] = self.new_location

        return result

    def to_flat_dict(self) -> dict:
        """Flat representation for CSV output."""
        return {
            "sku": self.sku,
            "status": self.status,
            "name": self.name,
            "old_quantity": self.old_quantity,
            "new_quantity": self.new_quantity,
            "quantity_delta": self.quantity_delta,
            "name_changed": self.name_changed,
            "old_name": self.old_name,
            "new_name": self.new_name,
            "location_changed": self.location_changed,
            "old_location": self.old_location,
            "new_location": self.new_location,
        }


@dataclass
class ReconciliationResult:
    """Complete reconciliation output."""

    added: list[ItemChange] = field(default_factory=list)
    removed: list[ItemChange] = field(default_factory=list)
    changed: list[ItemChange] = field(default_factory=list)
    unchanged: list[ItemChange] = field(default_factory=list)
    quality_issues: list[QualityIssue] = field(default_factory=list)
    skipped_skus: list[str] = field(default_factory=list)

    @property
    def summary(self) -> dict:
        return {
            "total_snapshot_1": len(self.removed) + len(self.changed) + len(self.unchanged),
            "total_snapshot_2": len(self.added) + len(self.changed) + len(self.unchanged),
            "added": len(self.added),
            "removed": len(self.removed),
            "changed": len(self.changed),
            "unchanged": len(self.unchanged),
            "quality_issues": len(self.quality_issues),
            "skipped_due_to_errors": len(self.skipped_skus),
        }

    @property
    def all_items(self) -> list[ItemChange]:
        return self.added + self.removed + self.changed + self.unchanged
