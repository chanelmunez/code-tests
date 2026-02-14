"""Tests for the core reconciliation logic."""

import pandas as pd
import pytest

from reconciliation.reconciler import reconcile


class TestReconcileBasic:
    """Tests for standard reconciliation scenarios."""

    def test_identifies_added_items(self, clean_snapshot_1, clean_snapshot_2):
        result = reconcile(clean_snapshot_1, clean_snapshot_2)
        added_skus = {item.sku for item in result.added}
        assert added_skus == {"SKU-006"}

    def test_identifies_removed_items(self, clean_snapshot_1, clean_snapshot_2):
        result = reconcile(clean_snapshot_1, clean_snapshot_2)
        removed_skus = {item.sku for item in result.removed}
        assert removed_skus == {"SKU-004"}

    def test_identifies_changed_items(self, clean_snapshot_1, clean_snapshot_2):
        result = reconcile(clean_snapshot_1, clean_snapshot_2)
        changed_skus = {item.sku for item in result.changed}
        # SKU-001 (100→90), SKU-003 (200→210), SKU-005 (500→480)
        assert changed_skus == {"SKU-001", "SKU-003", "SKU-005"}

    def test_identifies_unchanged_items(self, clean_snapshot_1, clean_snapshot_2):
        result = reconcile(clean_snapshot_1, clean_snapshot_2)
        unchanged_skus = {item.sku for item in result.unchanged}
        assert unchanged_skus == {"SKU-002"}

    def test_quantity_delta_correct(self, clean_snapshot_1, clean_snapshot_2):
        result = reconcile(clean_snapshot_1, clean_snapshot_2)
        sku001 = next(i for i in result.changed if i.sku == "SKU-001")
        assert sku001.old_quantity == 100
        assert sku001.new_quantity == 90
        assert sku001.quantity_delta == -10

    def test_added_item_has_new_quantity(self, clean_snapshot_1, clean_snapshot_2):
        result = reconcile(clean_snapshot_1, clean_snapshot_2)
        sku006 = next(i for i in result.added if i.sku == "SKU-006")
        assert sku006.new_quantity == 100
        assert sku006.old_quantity is None

    def test_removed_item_has_old_quantity(self, clean_snapshot_1, clean_snapshot_2):
        result = reconcile(clean_snapshot_1, clean_snapshot_2)
        sku004 = next(i for i in result.removed if i.sku == "SKU-004")
        assert sku004.old_quantity == 30
        assert sku004.new_quantity is None


class TestReconcileNameAndLocationChanges:
    """Tests for detecting name and location changes."""

    def test_detects_name_change(self):
        df1 = pd.DataFrame({
            "sku": ["SKU-001"],
            "name": ["Widget Pro"],
            "quantity": [100],
            "location": ["Warehouse A"],
            "date": ["2024-01-08"],
        })
        df2 = pd.DataFrame({
            "sku": ["SKU-001"],
            "name": ["Widget Professional"],
            "quantity": [100],
            "location": ["Warehouse A"],
            "date": ["2024-01-15"],
        })
        result = reconcile(df1, df2)
        assert len(result.changed) == 1
        item = result.changed[0]
        assert item.name_changed is True
        assert item.old_name == "Widget Pro"
        assert item.new_name == "Widget Professional"

    def test_detects_location_change(self):
        df1 = pd.DataFrame({
            "sku": ["SKU-001"],
            "name": ["Widget"],
            "quantity": [100],
            "location": ["Warehouse A"],
            "date": ["2024-01-08"],
        })
        df2 = pd.DataFrame({
            "sku": ["SKU-001"],
            "name": ["Widget"],
            "quantity": [100],
            "location": ["Warehouse B"],
            "date": ["2024-01-15"],
        })
        result = reconcile(df1, df2)
        assert len(result.changed) == 1
        item = result.changed[0]
        assert item.location_changed is True
        assert item.old_location == "Warehouse A"
        assert item.new_location == "Warehouse B"

    def test_multiple_changes_on_same_item(self):
        df1 = pd.DataFrame({
            "sku": ["SKU-001"],
            "name": ["Old Name"],
            "quantity": [100],
            "location": ["Warehouse A"],
            "date": ["2024-01-08"],
        })
        df2 = pd.DataFrame({
            "sku": ["SKU-001"],
            "name": ["New Name"],
            "quantity": [50],
            "location": ["Warehouse B"],
            "date": ["2024-01-15"],
        })
        result = reconcile(df1, df2)
        item = result.changed[0]
        assert item.quantity_delta == -50
        assert item.name_changed is True
        assert item.location_changed is True


class TestReconcileDuplicateHandling:
    """Tests for duplicate SKU exclusion."""

    def test_excludes_duplicate_skus_from_snapshot_2(self):
        df1 = pd.DataFrame({
            "sku": ["SKU-001", "SKU-002"],
            "name": ["Widget A", "Widget B"],
            "quantity": [100, 50],
            "location": ["Warehouse A", "Warehouse A"],
            "date": ["2024-01-08", "2024-01-08"],
        })
        df2 = pd.DataFrame({
            "sku": ["SKU-001", "SKU-002", "SKU-002"],
            "name": ["Widget A", "Widget B", "Widget B Alt"],
            "quantity": [90, 45, 10],
            "location": ["Warehouse A", "Warehouse A", "Warehouse B"],
            "date": ["2024-01-15", "2024-01-15", "2024-01-15"],
        })
        result = reconcile(df1, df2)
        # SKU-002 should be excluded entirely
        all_skus = {item.sku for item in result.all_items}
        assert "SKU-002" not in all_skus
        assert "SKU-002" in result.skipped_skus
        # SKU-001 should be in changed (100→90)
        assert len(result.changed) == 1
        assert result.changed[0].sku == "SKU-001"

    def test_excludes_duplicate_skus_from_snapshot_1(self):
        df1 = pd.DataFrame({
            "sku": ["SKU-001", "SKU-001", "SKU-002"],
            "name": ["Widget A", "Widget A2", "Widget B"],
            "quantity": [100, 50, 50],
            "location": ["Warehouse A", "Warehouse B", "Warehouse A"],
            "date": ["2024-01-08", "2024-01-08", "2024-01-08"],
        })
        df2 = pd.DataFrame({
            "sku": ["SKU-001", "SKU-002"],
            "name": ["Widget A", "Widget B"],
            "quantity": [90, 50],
            "location": ["Warehouse A", "Warehouse A"],
            "date": ["2024-01-15", "2024-01-15"],
        })
        result = reconcile(df1, df2)
        all_skus = {item.sku for item in result.all_items}
        assert "SKU-001" not in all_skus
        assert "SKU-001" in result.skipped_skus

    def test_skipped_skus_are_sorted(self):
        df1 = pd.DataFrame({
            "sku": ["SKU-003", "SKU-003", "SKU-001", "SKU-001"],
            "name": ["C", "C2", "A", "A2"],
            "quantity": [10, 20, 30, 40],
            "location": ["WA"] * 4,
            "date": ["2024-01-08"] * 4,
        })
        df2 = pd.DataFrame({
            "sku": ["SKU-002"],
            "name": ["B"],
            "quantity": [50],
            "location": ["WA"],
            "date": ["2024-01-15"],
        })
        result = reconcile(df1, df2)
        assert result.skipped_skus == ["SKU-001", "SKU-003"]


class TestReconcileErrorSeverityExclusion:
    """Tests for error-level quality issue exclusion."""

    def test_excludes_skus_with_negative_quantity_error(self):
        """SKUs flagged with error-level issues should be excluded from reconciliation."""
        from reconciliation.models import QualityIssue
        df1 = pd.DataFrame({
            "sku": ["SKU-001", "SKU-002"],
            "name": ["A", "B"],
            "quantity": [100, 50],
            "location": ["WA", "WA"],
            "date": ["2024-01-08", "2024-01-08"],
        })
        df2 = pd.DataFrame({
            "sku": ["SKU-001", "SKU-002"],
            "name": ["A", "B"],
            "quantity": [90, -5],
            "location": ["WA", "WA"],
            "date": ["2024-01-15", "2024-01-15"],
        })
        issues = [QualityIssue(
            sku="SKU-002", field="quantity", issue_type="negative_quantity",
            detail="Negative quantity: -5", snapshot="snapshot_2", severity="error",
        )]
        result = reconcile(df1, df2, quality_issues=issues)
        all_skus = {item.sku for item in result.all_items}
        assert "SKU-002" not in all_skus
        assert "SKU-002" in result.skipped_skus
        assert len(result.changed) == 1
        assert result.changed[0].sku == "SKU-001"

    def test_warning_level_issues_do_not_cause_exclusion(self):
        """Warning-level issues should NOT cause SKU exclusion."""
        from reconciliation.models import QualityIssue
        df1 = pd.DataFrame({
            "sku": ["SKU-001"],
            "name": ["A"],
            "quantity": [100],
            "location": ["WA"],
            "date": ["2024-01-08"],
        })
        df2 = df1.copy()
        df2["quantity"] = [90]
        issues = [QualityIssue(
            sku="SKU-001", field="quantity", issue_type="float_quantity",
            detail="Stored as float", snapshot="snapshot_2", severity="warning",
        )]
        result = reconcile(df1, df2, quality_issues=issues)
        assert len(result.changed) == 1

    def test_normalization_collision_creates_duplicate(self):
        """SKU-005 and SKU005 both normalizing to SKU-005 should be treated as duplicate."""
        df1 = pd.DataFrame({
            "sku": ["SKU-005", "SKU-005"],
            "name": ["Cable 6ft", "Cable 6ft Alt"],
            "quantity": [100, 50],
            "location": ["WA", "WB"],
            "date": ["2024-01-08", "2024-01-08"],
        })
        df2 = pd.DataFrame({
            "sku": ["SKU-005"],
            "name": ["Cable 6ft"],
            "quantity": [90],
            "location": ["WA"],
            "date": ["2024-01-15"],
        })
        result = reconcile(df1, df2)
        assert "SKU-005" in result.skipped_skus
        assert len(result.all_items) == 0


class TestReconcileEdgeCases:
    """Tests for edge cases."""

    def test_empty_snapshots(self):
        empty = pd.DataFrame(columns=["sku", "name", "quantity", "location", "date"])
        result = reconcile(empty, empty)
        assert len(result.all_items) == 0

    def test_all_items_removed(self):
        df1 = pd.DataFrame({
            "sku": ["SKU-001", "SKU-002"],
            "name": ["A", "B"],
            "quantity": [10, 20],
            "location": ["WA", "WA"],
            "date": ["2024-01-08", "2024-01-08"],
        })
        empty = pd.DataFrame(columns=["sku", "name", "quantity", "location", "date"])
        result = reconcile(df1, empty)
        assert len(result.removed) == 2
        assert len(result.added) == 0

    def test_all_items_added(self):
        empty = pd.DataFrame(columns=["sku", "name", "quantity", "location", "date"])
        df2 = pd.DataFrame({
            "sku": ["SKU-001", "SKU-002"],
            "name": ["A", "B"],
            "quantity": [10, 20],
            "location": ["WA", "WA"],
            "date": ["2024-01-15", "2024-01-15"],
        })
        result = reconcile(empty, df2)
        assert len(result.added) == 2
        assert len(result.removed) == 0

    def test_identical_snapshots(self, clean_snapshot_1):
        result = reconcile(clean_snapshot_1, clean_snapshot_1.copy())
        assert len(result.unchanged) == 5
        assert len(result.changed) == 0
        assert len(result.added) == 0
        assert len(result.removed) == 0

    def test_preserves_quality_issues_passed_in(self, clean_snapshot_1):
        from reconciliation.models import QualityIssue
        existing = [QualityIssue(
            sku="SKU-001", field="name", issue_type="whitespace",
            detail="test", snapshot="test",
        )]
        result = reconcile(clean_snapshot_1, clean_snapshot_1.copy(), quality_issues=existing)
        assert len(result.quality_issues) == 1


class TestReconcileCompositeKey:
    """Tests for SKU+location composite key mode."""

    def test_same_sku_different_locations_not_duplicate(self):
        """In sku_location mode, same SKU in different warehouses are separate items."""
        df1 = pd.DataFrame({
            "sku": ["SKU-001", "SKU-001"],
            "name": ["Widget", "Widget"],
            "quantity": [100, 50],
            "location": ["Warehouse A", "Warehouse B"],
            "date": ["2024-01-08", "2024-01-08"],
        })
        df2 = pd.DataFrame({
            "sku": ["SKU-001", "SKU-001"],
            "name": ["Widget", "Widget"],
            "quantity": [90, 45],
            "location": ["Warehouse A", "Warehouse B"],
            "date": ["2024-01-15", "2024-01-15"],
        })
        result = reconcile(df1, df2, key_mode="sku_location")
        assert len(result.changed) == 2
        assert len(result.skipped_skus) == 0

    def test_same_sku_same_location_is_duplicate_in_composite(self):
        """In sku_location mode, duplicate (sku, location) pairs are excluded."""
        df1 = pd.DataFrame({
            "sku": ["SKU-001", "SKU-001"],
            "name": ["Widget", "Widget v2"],
            "quantity": [100, 50],
            "location": ["Warehouse A", "Warehouse A"],
            "date": ["2024-01-08", "2024-01-08"],
        })
        df2 = pd.DataFrame({
            "sku": ["SKU-001"],
            "name": ["Widget"],
            "quantity": [90],
            "location": ["Warehouse A"],
            "date": ["2024-01-15"],
        })
        result = reconcile(df1, df2, key_mode="sku_location")
        assert "SKU-001|Warehouse A" in result.skipped_skus

    def test_composite_detects_location_transfer(self):
        """Item appears in new location (added) and disappears from old (removed)."""
        df1 = pd.DataFrame({
            "sku": ["SKU-001"],
            "name": ["Widget"],
            "quantity": [100],
            "location": ["Warehouse A"],
            "date": ["2024-01-08"],
        })
        df2 = pd.DataFrame({
            "sku": ["SKU-001"],
            "name": ["Widget"],
            "quantity": [100],
            "location": ["Warehouse B"],
            "date": ["2024-01-15"],
        })
        result = reconcile(df1, df2, key_mode="sku_location")
        assert len(result.removed) == 1
        assert result.removed[0].sku == "SKU-001"
        assert len(result.added) == 1
        assert result.added[0].sku == "SKU-001"

    def test_composite_unchanged(self):
        """Identical items at same locations are unchanged."""
        df1 = pd.DataFrame({
            "sku": ["SKU-001"],
            "name": ["Widget"],
            "quantity": [100],
            "location": ["Warehouse A"],
            "date": ["2024-01-08"],
        })
        df2 = df1.copy()
        result = reconcile(df1, df2, key_mode="sku_location")
        assert len(result.unchanged) == 1

    def test_sku_mode_flags_multi_location_as_duplicate(self):
        """In default sku mode, same SKU in different locations is a duplicate."""
        df1 = pd.DataFrame({
            "sku": ["SKU-001", "SKU-001"],
            "name": ["Widget", "Widget"],
            "quantity": [100, 50],
            "location": ["Warehouse A", "Warehouse B"],
            "date": ["2024-01-08", "2024-01-08"],
        })
        df2 = pd.DataFrame({
            "sku": ["SKU-001"],
            "name": ["Widget"],
            "quantity": [90],
            "location": ["Warehouse A"],
            "date": ["2024-01-15"],
        })
        result = reconcile(df1, df2, key_mode="sku")
        assert "SKU-001" in result.skipped_skus


class TestReconcileFuzzyNameMatching:
    """Tests for fuzzy name similarity scoring."""

    def test_similar_names_high_score(self):
        """'Multimeter Pro' → 'Multimeter Professional' should have high similarity."""
        df1 = pd.DataFrame({
            "sku": ["SKU-001"], "name": ["Multimeter Pro"],
            "quantity": [40], "location": ["WA"], "date": ["2024-01-08"],
        })
        df2 = pd.DataFrame({
            "sku": ["SKU-001"], "name": ["Multimeter Professional"],
            "quantity": [35], "location": ["WA"], "date": ["2024-01-15"],
        })
        result = reconcile(df1, df2)
        item = result.changed[0]
        assert item.status == "changed"
        assert item.name_changed is True
        assert item.old_name == "Multimeter Pro"
        assert item.new_name == "Multimeter Professional"
        assert item.name_similarity is not None
        assert 0.0 <= item.name_similarity <= 1.0
        assert item.name_similarity > 0.7

    def test_different_names_low_score(self):
        """Completely different names should have a low similarity score."""
        df1 = pd.DataFrame({
            "sku": ["SKU-001"], "name": ["Widget Alpha"],
            "quantity": [100], "location": ["WA"], "date": ["2024-01-08"],
        })
        df2 = pd.DataFrame({
            "sku": ["SKU-001"], "name": ["Zebra Connector"],
            "quantity": [95], "location": ["WA"], "date": ["2024-01-15"],
        })
        result = reconcile(df1, df2)
        item = result.changed[0]
        assert item.name_similarity is not None
        assert item.name_similarity < 0.5

    def test_identical_names_no_similarity_score(self):
        """When names match, name_similarity should be None."""
        df1 = pd.DataFrame({
            "sku": ["SKU-001"], "name": ["Widget"],
            "quantity": [100], "location": ["WA"], "date": ["2024-01-08"],
        })
        df2 = pd.DataFrame({
            "sku": ["SKU-001"], "name": ["Widget"],
            "quantity": [90], "location": ["WA"], "date": ["2024-01-15"],
        })
        result = reconcile(df1, df2)
        item = result.changed[0]
        assert item.name_changed is False
        assert item.name_similarity is None

    def test_similarity_in_to_dict(self):
        """Similarity score should appear in to_dict output when name changed."""
        df1 = pd.DataFrame({
            "sku": ["SKU-001"], "name": ["Cable 6ft"],
            "quantity": [100], "location": ["WA"], "date": ["2024-01-08"],
        })
        df2 = pd.DataFrame({
            "sku": ["SKU-001"], "name": ["Cable 6 ft"],
            "quantity": [100], "location": ["WA"], "date": ["2024-01-15"],
        })
        result = reconcile(df1, df2)
        d = result.changed[0].to_dict()
        assert "name_similarity" in d
        assert d["name_similarity"] > 0.8

    def test_similarity_in_flat_dict(self):
        """Similarity score should appear in to_flat_dict for CSV output."""
        df1 = pd.DataFrame({
            "sku": ["SKU-001"], "name": ["Widget Pro"],
            "quantity": [100], "location": ["WA"], "date": ["2024-01-08"],
        })
        df2 = pd.DataFrame({
            "sku": ["SKU-001"], "name": ["Widget Professional"],
            "quantity": [90], "location": ["WA"], "date": ["2024-01-15"],
        })
        result = reconcile(df1, df2)
        flat = result.changed[0].to_flat_dict()
        assert "name_similarity" in flat


class TestReconcileTolerance:
    """Tests for variance tolerance bands."""

    def _make_pair(self, qty1, qty2):
        df1 = pd.DataFrame({
            "sku": ["SKU-001"],
            "name": ["Widget"],
            "quantity": [qty1],
            "location": ["WA"],
            "date": ["2024-01-08"],
        })
        df2 = pd.DataFrame({
            "sku": ["SKU-001"],
            "name": ["Widget"],
            "quantity": [qty2],
            "location": ["WA"],
            "date": ["2024-01-15"],
        })
        return df1, df2

    def test_no_tolerance_default(self):
        """With default tolerance=0, any delta is a change."""
        df1, df2 = self._make_pair(100, 99)
        result = reconcile(df1, df2)
        assert len(result.changed) == 1
        assert len(result.within_tolerance) == 0

    def test_absolute_tolerance_within(self):
        """Delta of 5 is within absolute tolerance of 5."""
        df1, df2 = self._make_pair(100, 95)
        result = reconcile(df1, df2, tolerance=5)
        assert len(result.within_tolerance) == 1
        assert len(result.changed) == 0
        assert result.within_tolerance[0].status == "within_tolerance"
        assert result.within_tolerance[0].quantity_delta == -5

    def test_absolute_tolerance_exceeds(self):
        """Delta of 6 exceeds absolute tolerance of 5."""
        df1, df2 = self._make_pair(100, 94)
        result = reconcile(df1, df2, tolerance=5)
        assert len(result.changed) == 1
        assert len(result.within_tolerance) == 0

    def test_percentage_tolerance_within(self):
        """Delta of 2% is within 5% tolerance."""
        df1, df2 = self._make_pair(1000, 980)
        result = reconcile(df1, df2, tolerance_pct=5.0)
        assert len(result.within_tolerance) == 1
        assert len(result.changed) == 0

    def test_percentage_tolerance_exceeds(self):
        """Delta of 10% exceeds 5% tolerance."""
        df1, df2 = self._make_pair(100, 90)
        result = reconcile(df1, df2, tolerance_pct=5.0)
        assert len(result.changed) == 1
        assert len(result.within_tolerance) == 0

    def test_name_change_not_tolerated(self):
        """Name changes are never within tolerance, even if qty delta is small."""
        df1 = pd.DataFrame({
            "sku": ["SKU-001"], "name": ["Widget Pro"],
            "quantity": [100], "location": ["WA"], "date": ["2024-01-08"],
        })
        df2 = pd.DataFrame({
            "sku": ["SKU-001"], "name": ["Widget Professional"],
            "quantity": [99], "location": ["WA"], "date": ["2024-01-15"],
        })
        result = reconcile(df1, df2, tolerance=5)
        assert len(result.changed) == 1
        assert len(result.within_tolerance) == 0

    def test_within_tolerance_counted_in_summary(self):
        """within_tolerance items count towards snapshot totals."""
        df1, df2 = self._make_pair(100, 99)
        result = reconcile(df1, df2, tolerance=5)
        s = result.summary
        assert s["within_tolerance"] == 1
        assert s["changed"] == 0
        assert s["total_snapshot_1"] == 1
        assert s["total_snapshot_2"] == 1


class TestReconcilePriority:
    """Tests for priority assignment on changed items."""

    def test_high_priority_for_large_variance(self):
        """Greater than 10% change = high priority."""
        df1 = pd.DataFrame({
            "sku": ["SKU-001"], "name": ["Widget"],
            "quantity": [100], "location": ["WA"], "date": ["2024-01-08"],
        })
        df2 = pd.DataFrame({
            "sku": ["SKU-001"], "name": ["Widget"],
            "quantity": [80], "location": ["WA"], "date": ["2024-01-15"],
        })
        result = reconcile(df1, df2)
        assert result.changed[0].priority == "high"

    def test_medium_priority_for_moderate_variance(self):
        """5-10% change = medium priority."""
        df1 = pd.DataFrame({
            "sku": ["SKU-001"], "name": ["Widget"],
            "quantity": [100], "location": ["WA"], "date": ["2024-01-08"],
        })
        df2 = pd.DataFrame({
            "sku": ["SKU-001"], "name": ["Widget"],
            "quantity": [93], "location": ["WA"], "date": ["2024-01-15"],
        })
        result = reconcile(df1, df2)
        assert result.changed[0].priority == "medium"

    def test_low_priority_for_small_variance(self):
        """Less than 5% change = low priority."""
        df1 = pd.DataFrame({
            "sku": ["SKU-001"], "name": ["Widget"],
            "quantity": [100], "location": ["WA"], "date": ["2024-01-08"],
        })
        df2 = pd.DataFrame({
            "sku": ["SKU-001"], "name": ["Widget"],
            "quantity": [97], "location": ["WA"], "date": ["2024-01-15"],
        })
        result = reconcile(df1, df2)
        assert result.changed[0].priority == "low"

    def test_high_priority_for_name_change(self):
        """Any name change = high priority regardless of qty delta."""
        df1 = pd.DataFrame({
            "sku": ["SKU-001"], "name": ["Widget Pro"],
            "quantity": [100], "location": ["WA"], "date": ["2024-01-08"],
        })
        df2 = pd.DataFrame({
            "sku": ["SKU-001"], "name": ["Widget Professional"],
            "quantity": [99], "location": ["WA"], "date": ["2024-01-15"],
        })
        result = reconcile(df1, df2)
        assert result.changed[0].priority == "high"

    def test_unchanged_has_no_priority(self, clean_snapshot_1):
        result = reconcile(clean_snapshot_1, clean_snapshot_1.copy())
        for item in result.unchanged:
            assert item.priority is None


class TestReconcileHealthScore:
    """Tests for inventory health statistics."""

    def test_accuracy_rate_all_unchanged(self):
        """100% accuracy when nothing changed."""
        df = pd.DataFrame({
            "sku": ["SKU-001", "SKU-002"],
            "name": ["A", "B"],
            "quantity": [100, 50],
            "location": ["WA", "WA"],
            "date": ["2024-01-08", "2024-01-08"],
        })
        result = reconcile(df, df.copy())
        assert result.health["accuracy_rate"] == 100.0

    def test_accuracy_rate_with_changes(self, clean_snapshot_1, clean_snapshot_2):
        """Accuracy < 100 when items changed."""
        result = reconcile(clean_snapshot_1, clean_snapshot_2)
        health = result.health
        # 1 unchanged out of 4 common items = 25%
        assert health["accuracy_rate"] == 25.0

    def test_total_variance(self, clean_snapshot_1, clean_snapshot_2):
        """Total variance sums absolute deltas."""
        result = reconcile(clean_snapshot_1, clean_snapshot_2)
        # SKU-001: |90-100|=10, SKU-003: |210-200|=10, SKU-005: |480-500|=20
        assert result.health["total_variance"] == 40

    def test_data_quality_score_clean_data(self, clean_snapshot_1, clean_snapshot_2):
        """Clean data should have high quality score."""
        result = reconcile(clean_snapshot_1, clean_snapshot_2)
        assert result.health["data_quality_score"] == 100.0

    def test_data_quality_score_with_issues(self):
        """Quality score decreases with issues."""
        from reconciliation.models import QualityIssue
        df = pd.DataFrame({
            "sku": ["SKU-001", "SKU-002"],
            "name": ["A", "B"],
            "quantity": [100, 50],
            "location": ["WA", "WA"],
            "date": ["2024-01-08", "2024-01-08"],
        })
        issues = [
            QualityIssue(sku="SKU-001", field="name", issue_type="whitespace",
                         detail="test", snapshot="snap1"),
        ]
        result = reconcile(df, df.copy(), quality_issues=issues)
        assert result.health["data_quality_score"] < 100.0

    def test_health_in_json_report(self, tmp_path, clean_snapshot_1, clean_snapshot_2):
        """Health stats should appear in JSON report with valid values."""
        from reconciliation.reporter import generate_json_report
        import json
        result = reconcile(clean_snapshot_1, clean_snapshot_2)
        out = tmp_path / "report.json"
        generate_json_report(result, out)
        data = json.loads(out.read_text())
        health = data["health"]
        assert 0 <= health["accuracy_rate"] <= 100
        assert health["total_variance"] >= 0
        assert 0 <= health["data_quality_score"] <= 100
        assert isinstance(health["variance_by_location"], dict)


class TestReconcileSummary:
    """Tests for the summary property."""

    def test_summary_counts(self, clean_snapshot_1, clean_snapshot_2):
        result = reconcile(clean_snapshot_1, clean_snapshot_2)
        summary = result.summary
        assert summary["added"] == 1
        assert summary["removed"] == 1
        assert summary["changed"] == 3
        assert summary["unchanged"] == 1
        assert summary["total_snapshot_1"] == 5  # 1 removed + 3 changed + 1 unchanged
        assert summary["total_snapshot_2"] == 5  # 1 added + 3 changed + 1 unchanged
