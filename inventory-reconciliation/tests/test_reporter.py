"""Tests for the report generation module."""

import csv
import json
from pathlib import Path

import pytest

from reconciliation.models import ItemChange, QualityIssue, ReconciliationResult
from reconciliation.reporter import generate_csv_report, generate_json_report, _apply_filters


@pytest.fixture
def sample_result() -> ReconciliationResult:
    """A small ReconciliationResult for testing report output."""
    return ReconciliationResult(
        added=[ItemChange(sku="SKU-006", status="added", name="Cable 10ft", new_quantity=100)],
        removed=[ItemChange(sku="SKU-004", status="removed", name="Gadget Lite", old_quantity=30)],
        changed=[ItemChange(
            sku="SKU-001", status="changed", name="Widget A",
            old_quantity=100, new_quantity=90, quantity_delta=-10,
        )],
        unchanged=[ItemChange(
            sku="SKU-002", status="unchanged", name="Widget B",
            old_quantity=50, new_quantity=50, quantity_delta=0,
        )],
        quality_issues=[QualityIssue(
            sku="SKU-005", field="sku", issue_type="sku_format",
            detail="test issue", snapshot="snapshot_2",
            original_value="SKU005", corrected_value="SKU-005",
        )],
        skipped_skus=["SKU-045"],
    )


class TestJsonReport:
    """Tests for JSON report generation."""

    def test_creates_file(self, tmp_path, sample_result):
        out = tmp_path / "report.json"
        generate_json_report(sample_result, out)
        assert out.exists()

    def test_valid_json(self, tmp_path, sample_result):
        out = tmp_path / "report.json"
        generate_json_report(sample_result, out)
        data = json.loads(out.read_text())
        assert isinstance(data, dict)

    def test_contains_all_sections(self, tmp_path, sample_result):
        out = tmp_path / "report.json"
        generate_json_report(sample_result, out)
        data = json.loads(out.read_text())
        assert "metadata" in data
        assert "summary" in data
        assert "reconciliation" in data
        assert "quality_issues" in data
        assert "skipped_skus" in data
        assert "pipeline_log" in data

    def test_summary_counts(self, tmp_path, sample_result):
        out = tmp_path / "report.json"
        generate_json_report(sample_result, out)
        data = json.loads(out.read_text())
        assert data["summary"]["added"] == 1
        assert data["summary"]["removed"] == 1
        assert data["summary"]["changed"] == 1
        assert data["summary"]["unchanged"] == 1

    def test_reconciliation_categories(self, tmp_path, sample_result):
        out = tmp_path / "report.json"
        generate_json_report(sample_result, out)
        data = json.loads(out.read_text())
        recon = data["reconciliation"]
        assert len(recon["added"]) == 1
        assert recon["added"][0]["sku"] == "SKU-006"
        assert len(recon["removed"]) == 1
        assert recon["removed"][0]["sku"] == "SKU-004"

    def test_quality_issues_included(self, tmp_path, sample_result):
        out = tmp_path / "report.json"
        generate_json_report(sample_result, out)
        data = json.loads(out.read_text())
        assert len(data["quality_issues"]) == 1
        assert data["quality_issues"][0]["issue_type"] == "sku_format"

    def test_skipped_skus_included(self, tmp_path, sample_result):
        out = tmp_path / "report.json"
        generate_json_report(sample_result, out)
        data = json.loads(out.read_text())
        assert data["skipped_skus"] == ["SKU-045"]

    def test_metadata_includes_paths(self, tmp_path, sample_result):
        out = tmp_path / "report.json"
        generate_json_report(sample_result, out, "data/snap1.csv", "data/snap2.csv")
        data = json.loads(out.read_text())
        assert data["metadata"]["snapshot_1"] == "data/snap1.csv"
        assert data["metadata"]["snapshot_2"] == "data/snap2.csv"

    def test_creates_parent_directories(self, tmp_path, sample_result):
        out = tmp_path / "nested" / "dir" / "report.json"
        generate_json_report(sample_result, out)
        assert out.exists()


class TestCsvReport:
    """Tests for CSV report generation."""

    def test_creates_file(self, tmp_path, sample_result):
        out = tmp_path / "summary.csv"
        generate_csv_report(sample_result, out)
        assert out.exists()

    def test_has_correct_header(self, tmp_path, sample_result):
        out = tmp_path / "summary.csv"
        generate_csv_report(sample_result, out)
        with open(out) as f:
            reader = csv.reader(f)
            header = next(reader)
        assert "sku" in header
        assert "status" in header
        assert "quantity_delta" in header

    def test_row_count(self, tmp_path, sample_result):
        out = tmp_path / "summary.csv"
        generate_csv_report(sample_result, out)
        with open(out) as f:
            reader = csv.DictReader(f)
            rows = list(reader)
        # 1 added + 1 removed + 1 changed + 1 unchanged = 4
        assert len(rows) == 4

    def test_statuses_present(self, tmp_path, sample_result):
        out = tmp_path / "summary.csv"
        generate_csv_report(sample_result, out)
        with open(out) as f:
            reader = csv.DictReader(f)
            statuses = {row["status"] for row in reader}
        assert statuses == {"added", "removed", "changed", "unchanged"}

    def test_quantity_delta_for_changed(self, tmp_path, sample_result):
        out = tmp_path / "summary.csv"
        generate_csv_report(sample_result, out)
        with open(out) as f:
            reader = csv.DictReader(f)
            changed = [r for r in reader if r["status"] == "changed"]
        assert changed[0]["quantity_delta"] == "-10"

    def test_creates_parent_directories(self, tmp_path, sample_result):
        out = tmp_path / "nested" / "dir" / "summary.csv"
        generate_csv_report(sample_result, out)
        assert out.exists()

    def test_csv_has_priority_column(self, tmp_path, sample_result):
        out = tmp_path / "summary.csv"
        generate_csv_report(sample_result, out)
        with open(out) as f:
            reader = csv.reader(f)
            header = next(reader)
        assert "priority" in header

    def test_csv_sort_by_delta(self, tmp_path):
        result = ReconciliationResult(
            changed=[
                ItemChange(sku="SKU-001", status="changed", name="A",
                           old_quantity=100, new_quantity=90, quantity_delta=-10, priority="medium"),
                ItemChange(sku="SKU-002", status="changed", name="B",
                           old_quantity=200, new_quantity=150, quantity_delta=-50, priority="high"),
            ],
        )
        out = tmp_path / "sorted.csv"
        generate_csv_report(result, out, sort_by="delta")
        with open(out) as f:
            rows = list(csv.DictReader(f))
        # Largest delta first
        assert rows[0]["sku"] == "SKU-002"
        assert rows[1]["sku"] == "SKU-001"

    def test_csv_filter_status(self, tmp_path, sample_result):
        out = tmp_path / "filtered.csv"
        generate_csv_report(sample_result, out, filter_status="changed")
        with open(out) as f:
            rows = list(csv.DictReader(f))
        assert all(r["status"] == "changed" for r in rows)
        assert len(rows) == 1

    def test_csv_sort_by_priority(self, tmp_path):
        result = ReconciliationResult(
            changed=[
                ItemChange(sku="SKU-001", status="changed", name="A",
                           old_quantity=100, new_quantity=99, quantity_delta=-1, priority="low"),
                ItemChange(sku="SKU-002", status="changed", name="B",
                           old_quantity=200, new_quantity=150, quantity_delta=-50, priority="high"),
                ItemChange(sku="SKU-003", status="changed", name="C",
                           old_quantity=300, new_quantity=280, quantity_delta=-20, priority="medium"),
            ],
        )
        out = tmp_path / "priority.csv"
        generate_csv_report(result, out, sort_by="priority")
        with open(out) as f:
            rows = list(csv.DictReader(f))
        assert rows[0]["priority"] == "high"
        assert rows[1]["priority"] == "medium"
        assert rows[2]["priority"] == "low"


class TestApplyFilters:
    """Tests for the _apply_filters helper."""

    def test_filter_by_status(self):
        items = [
            ItemChange(sku="SKU-001", status="changed", name="A", quantity_delta=-5),
            ItemChange(sku="SKU-002", status="added", name="B"),
        ]
        filtered = _apply_filters(items, filter_status="added")
        assert len(filtered) == 1
        assert filtered[0].sku == "SKU-002"

    def test_sort_by_sku(self):
        items = [
            ItemChange(sku="SKU-003", status="changed", name="C"),
            ItemChange(sku="SKU-001", status="changed", name="A"),
        ]
        sorted_items = _apply_filters(items, sort_by="sku")
        assert sorted_items[0].sku == "SKU-001"
        assert sorted_items[1].sku == "SKU-003"

    def test_no_filters_returns_same(self):
        items = [ItemChange(sku="SKU-001", status="changed", name="A")]
        assert _apply_filters(items) == items
