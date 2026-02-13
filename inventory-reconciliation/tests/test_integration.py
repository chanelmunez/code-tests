"""Integration tests — run the full pipeline against real data."""

import json
import csv
from pathlib import Path

import pytest

from reconciliation.loader import load_snapshot
from reconciliation.normalizer import normalize_dataframe
from reconciliation.validator import validate_snapshot
from reconciliation.reconciler import reconcile
from reconciliation.reporter import generate_json_report, generate_csv_report

DATA_DIR = Path(__file__).parent.parent / "data"
SNAPSHOT_1 = DATA_DIR / "snapshot_1.csv"
SNAPSHOT_2 = DATA_DIR / "snapshot_2.csv"


@pytest.fixture
def full_reconciliation():
    """Run the full reconciliation pipeline on the real data files."""
    df1 = load_snapshot(SNAPSHOT_1)
    df2 = load_snapshot(SNAPSHOT_2)

    df1, issues_1 = normalize_dataframe(df1, "snapshot_1")
    df2, issues_2 = normalize_dataframe(df2, "snapshot_2")
    all_issues = issues_1 + issues_2

    all_issues.extend(validate_snapshot(df1, "snapshot_1"))
    all_issues.extend(validate_snapshot(df2, "snapshot_2"))

    return reconcile(df1, df2, quality_issues=all_issues)


class TestFullPipeline:
    """End-to-end tests on the real assessment data."""

    def test_loads_snapshot_1(self):
        df = load_snapshot(SNAPSHOT_1)
        assert len(df) == 75

    def test_loads_snapshot_2(self):
        df = load_snapshot(SNAPSHOT_2)
        # 80 SKUs minus SKU-025 and SKU-026 = 73 original + 5 new + 1 duplicate row = 79
        assert len(df) == 79

    def test_sku_normalization_fixes_known_issues(self):
        df = load_snapshot(SNAPSHOT_2)
        df, issues = normalize_dataframe(df, "snapshot_2")
        sku_issues = [i for i in issues if i.issue_type == "sku_format"]
        normalized_skus = set(df["sku"])
        # These malformed SKUs should now be in canonical form
        assert "SKU-005" in normalized_skus
        assert "SKU-008" in normalized_skus
        assert "SKU-018" in normalized_skus
        # And the originals should be flagged
        original_values = {i.original_value for i in sku_issues}
        assert "SKU005" in original_values
        assert "sku-008" in original_values
        assert "SKU018" in original_values

    def test_detects_duplicate_sku_045(self):
        df = load_snapshot(SNAPSHOT_2)
        df, _ = normalize_dataframe(df, "snapshot_2")
        issues = validate_snapshot(df, "snapshot_2")
        dup_issues = [i for i in issues if i.issue_type == "duplicate_sku"]
        dup_skus = {i.sku for i in dup_issues}
        assert "SKU-045" in dup_skus

    def test_detects_negative_quantity(self):
        df = load_snapshot(SNAPSHOT_2)
        df, _ = normalize_dataframe(df, "snapshot_2")
        issues = validate_snapshot(df, "snapshot_2")
        neg_issues = [i for i in issues if i.issue_type == "negative_quantity"]
        assert len(neg_issues) >= 1
        assert any(i.sku == "SKU-045" for i in neg_issues)

    def test_detects_date_format_issue(self):
        df = load_snapshot(SNAPSHOT_2)
        _, issues = normalize_dataframe(df, "snapshot_2")
        date_issues = [i for i in issues if i.issue_type == "date_format"]
        assert len(date_issues) >= 1
        assert any(i.original_value == "01/15/2024" for i in date_issues)

    def test_removed_items(self, full_reconciliation):
        removed_skus = {item.sku for item in full_reconciliation.removed}
        # SKU-025 (VGA Cable) and SKU-026 (DVI Cable) are not in snapshot_2
        assert "SKU-025" in removed_skus
        assert "SKU-026" in removed_skus

    def test_added_items(self, full_reconciliation):
        added_skus = {item.sku for item in full_reconciliation.added}
        # SKU-076 through SKU-080 are new in snapshot_2
        assert added_skus == {"SKU-076", "SKU-077", "SKU-078", "SKU-079", "SKU-080"}

    def test_sku_045_skipped_due_to_duplicate(self, full_reconciliation):
        all_skus = {item.sku for item in full_reconciliation.all_items}
        assert "SKU-045" not in all_skus
        assert "SKU-045" in full_reconciliation.skipped_skus

    def test_unchanged_items_exist(self, full_reconciliation):
        # SKU-006 has quantity 350 in both snapshots
        unchanged_skus = {item.sku for item in full_reconciliation.unchanged}
        assert "SKU-006" in unchanged_skus

    def test_changed_items_have_deltas(self, full_reconciliation):
        # SKU-001: 150 → 145 = -5
        sku001 = next(
            (i for i in full_reconciliation.changed if i.sku == "SKU-001"), None
        )
        assert sku001 is not None
        assert sku001.old_quantity == 150
        assert sku001.new_quantity == 145
        assert sku001.quantity_delta == -5

    def test_total_items_reconciled(self, full_reconciliation):
        summary = full_reconciliation.summary
        # 75 items in snap1, minus 1 skipped (SKU-045) = 74
        assert summary["total_snapshot_1"] == 74
        # 79 rows in snap2 (80 SKUs minus SKU-025/026, plus duplicate SKU-045 row).
        # 78 unique SKUs, minus 1 skipped (SKU-045) = 77 reconciled.
        assert summary["total_snapshot_2"] == 77

    def test_no_items_appear_in_multiple_categories(self, full_reconciliation):
        added = {i.sku for i in full_reconciliation.added}
        removed = {i.sku for i in full_reconciliation.removed}
        changed = {i.sku for i in full_reconciliation.changed}
        unchanged = {i.sku for i in full_reconciliation.unchanged}
        # No overlaps between any categories
        all_sets = [added, removed, changed, unchanged]
        for i, s1 in enumerate(all_sets):
            for s2 in all_sets[i + 1:]:
                assert s1.isdisjoint(s2), f"Overlap found: {s1 & s2}"

    def test_quality_issues_found(self, full_reconciliation):
        issue_types = {i.issue_type for i in full_reconciliation.quality_issues}
        assert "sku_format" in issue_types
        assert "duplicate_sku" in issue_types
        assert "negative_quantity" in issue_types
        assert "date_format" in issue_types


class TestReportGeneration:
    """Test that report files are correctly generated from real data."""

    def test_json_report_roundtrip(self, tmp_path, full_reconciliation):
        out = tmp_path / "report.json"
        generate_json_report(full_reconciliation, out, str(SNAPSHOT_1), str(SNAPSHOT_2))
        data = json.loads(out.read_text())
        assert data["summary"]["added"] == len(full_reconciliation.added)
        assert data["summary"]["removed"] == len(full_reconciliation.removed)
        assert len(data["quality_issues"]) == len(full_reconciliation.quality_issues)

    def test_csv_report_row_count(self, tmp_path, full_reconciliation):
        out = tmp_path / "summary.csv"
        generate_csv_report(full_reconciliation, out)
        with open(out) as f:
            rows = list(csv.DictReader(f))
        assert len(rows) == len(full_reconciliation.all_items)
