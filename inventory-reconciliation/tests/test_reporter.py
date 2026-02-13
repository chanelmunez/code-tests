"""Tests for the report generation module."""

import csv
import json
from pathlib import Path

import pytest

from reconciliation.models import ItemChange, QualityIssue, ReconciliationResult
from reconciliation.reporter import generate_csv_report, generate_json_report


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
