"""Tests for the CLI entry point (reconcile.py)."""

import csv
import json
import subprocess
import sys
from pathlib import Path

import pytest


PROJECT_DIR = Path(__file__).parent.parent


def _write_snapshot(path: Path, rows: list[tuple[str, str, int, str, str]]) -> None:
    with open(path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["sku", "name", "quantity", "location", "last_counted"])
        writer.writerows(rows)


class TestCli:
    """Test the reconcile.py script via subprocess."""

    def test_runs_successfully_with_defaults(self, tmp_path):
        result = subprocess.run(
            [
                sys.executable,
                "reconcile.py",
                "--allow-errors",
                "--output-dir",
                str(tmp_path),
            ],
            capture_output=True, text=True, cwd=PROJECT_DIR,
        )
        assert result.returncode == 0
        output = result.stdout + result.stderr
        assert "RECONCILIATION SUMMARY" in output

    def test_creates_output_files(self, tmp_path):
        result = subprocess.run(
            [
                sys.executable,
                "reconcile.py",
                "--output-dir",
                str(tmp_path),
                "--allow-errors",
            ],
            capture_output=True, text=True, cwd=PROJECT_DIR,
        )
        assert result.returncode == 0
        assert (tmp_path / "reconciliation_report.json").exists()
        assert (tmp_path / "reconciliation_summary.csv").exists()

    def test_json_output_is_valid(self, tmp_path):
        subprocess.run(
            [
                sys.executable,
                "reconcile.py",
                "--output-dir",
                str(tmp_path),
                "--allow-errors",
            ],
            capture_output=True, text=True, cwd=PROJECT_DIR,
        )
        report = json.loads((tmp_path / "reconciliation_report.json").read_text())
        assert "summary" in report
        assert "reconciliation" in report
        assert "quality_issues" in report

    def test_summary_output_counts(self, tmp_path):
        result = subprocess.run(
            [
                sys.executable,
                "reconcile.py",
                "--allow-errors",
                "--output-dir",
                str(tmp_path),
            ],
            capture_output=True, text=True, cwd=PROJECT_DIR,
        )
        output = result.stdout + result.stderr
        assert "Added" in output
        assert "Removed" in output
        assert "Changed" in output
        assert "Unchanged" in output
        assert "Skipped" in output

    def test_custom_snapshot_paths(self, tmp_path):
        # Create minimal valid CSVs
        snap1 = tmp_path / "s1.csv"
        snap2 = tmp_path / "s2.csv"
        snap1.write_text("sku,name,quantity,location,last_counted\nSKU-001,A,10,WA,2024-01-08\n")
        snap2.write_text("sku,product_name,qty,warehouse,updated_at\nSKU-001,A,8,WA,2024-01-15\n")

        out_dir = tmp_path / "out"
        result = subprocess.run(
            [
                sys.executable, "reconcile.py",
                "--snapshot1", str(snap1),
                "--snapshot2", str(snap2),
                "--output-dir", str(out_dir),
            ],
            capture_output=True, text=True, cwd=PROJECT_DIR,
        )
        assert result.returncode == 0
        report = json.loads((out_dir / "reconciliation_report.json").read_text())
        assert report["summary"]["changed"] == 1

    def test_json_log_format(self, tmp_path):
        result = subprocess.run(
            [
                sys.executable,
                "reconcile.py",
                "--log-format",
                "json",
                "--output-dir",
                str(tmp_path),
                "--allow-errors",
            ],
            capture_output=True, text=True, cwd=PROJECT_DIR,
        )
        assert result.returncode == 0
        # Each line of stderr should be valid JSON
        lines = [l for l in result.stderr.strip().split("\n") if l.strip()]
        json_lines = []
        for line in lines:
            try:
                json_lines.append(json.loads(line))
            except json.JSONDecodeError:
                pass
        assert len(json_lines) > 0
        messages = [j.get("message", "") for j in json_lines]
        assert any("Loading" in m for m in messages)

    def test_pipeline_log_in_json_report(self, tmp_path):
        subprocess.run(
            [
                sys.executable,
                "reconcile.py",
                "--output-dir",
                str(tmp_path),
                "--allow-errors",
            ],
            capture_output=True, text=True, cwd=PROJECT_DIR,
        )
        report = json.loads((tmp_path / "reconciliation_report.json").read_text())
        assert "pipeline_log" in report
        stages = [entry["stage"] for entry in report["pipeline_log"]]
        assert "load" in stages
        assert "normalize" in stages
        assert "validate" in stages
        assert "reconcile" in stages

    def test_nonexistent_file_exits_with_error(self):
        result = subprocess.run(
            [sys.executable, "reconcile.py", "--snapshot1", "does_not_exist.csv"],
            capture_output=True, text=True, cwd=PROJECT_DIR,
        )
        assert result.returncode != 0

    def test_fails_on_errors_by_default(self):
        result = subprocess.run(
            [sys.executable, "reconcile.py"],
            capture_output=True,
            text=True,
            cwd=PROJECT_DIR,
        )
        assert result.returncode != 0
        output = result.stdout + result.stderr
        assert "allow-errors" in output or "allow-errors" in result.stderr

    def test_allow_errors_flag_enables_reports(self, tmp_path):
        result = subprocess.run(
            [
                sys.executable,
                "reconcile.py",
                "--snapshot1",
                "data/snapshot_1.csv",
                "--snapshot2",
                "data/snapshot_2.csv",
                "--output-dir",
                str(tmp_path),
                "--allow-errors",
            ],
            capture_output=True,
            text=True,
            cwd=PROJECT_DIR,
        )
        assert result.returncode == 0
        assert (tmp_path / "reconciliation_report.json").exists()

    def test_cli_sort_and_filter_flags(self, tmp_path):
        snap1 = tmp_path / "snap1.csv"
        snap2 = tmp_path / "snap2.csv"
        _write_snapshot(snap1, [
            ("SKU-101", "Widget", 100, "WA", "2024-01-01"),
            ("SKU-102", "Gadget", 200, "WA", "2024-01-01"),
        ])
        _write_snapshot(snap2, [
            ("SKU-101", "Widget", 80, "WA", "2024-01-08"),
            ("SKU-102", "Gadget", 150, "WA", "2024-01-08"),
        ])
        out_dir = tmp_path / "out"
        result = subprocess.run(
            [
                sys.executable,
                "reconcile.py",
                "--snapshot1",
                str(snap1),
                "--snapshot2",
                str(snap2),
                "--output-dir",
                str(out_dir),
                "--sort",
                "delta",
                "--filter",
                "changed",
            ],
            capture_output=True,
            text=True,
            cwd=PROJECT_DIR,
        )
        assert result.returncode == 0
        csv_path = out_dir / "reconciliation_summary.csv"
        with open(csv_path) as f:
            rows = list(csv.DictReader(f))
        assert len(rows) == 2
        assert rows[0]["sku"] == "SKU-102"  # largest delta first
        assert rows[1]["sku"] == "SKU-101"

    def test_cli_tolerance_flag(self, tmp_path):
        snap1 = tmp_path / "tol1.csv"
        snap2 = tmp_path / "tol2.csv"
        _write_snapshot(snap1, [("SKU-201", "Cable", 100, "WA", "2024-01-01")])
        _write_snapshot(snap2, [("SKU-201", "Cable", 102, "WA", "2024-01-08")])
        out_dir = tmp_path / "out_tol"
        result = subprocess.run(
            [
                sys.executable,
                "reconcile.py",
                "--snapshot1",
                str(snap1),
                "--snapshot2",
                str(snap2),
                "--output-dir",
                str(out_dir),
                "--tolerance",
                "5",
            ],
            capture_output=True,
            text=True,
            cwd=PROJECT_DIR,
        )
        assert result.returncode == 0
        data = json.loads((out_dir / "reconciliation_report.json").read_text())
        assert data["summary"]["within_tolerance"] == 1

    def test_cli_composite_key_mode(self, tmp_path):
        snap1 = tmp_path / "loc1.csv"
        snap2 = tmp_path / "loc2.csv"
        _write_snapshot(snap1, [("SKU-301", "Widget", 50, "WA", "2024-01-01")])
        _write_snapshot(snap2, [("SKU-301", "Widget", 60, "WB", "2024-01-08")])
        out_dir = tmp_path / "out_loc"
        result = subprocess.run(
            [
                sys.executable,
                "reconcile.py",
                "--snapshot1",
                str(snap1),
                "--snapshot2",
                str(snap2),
                "--output-dir",
                str(out_dir),
                "--key-mode",
                "sku_location",
            ],
            capture_output=True,
            text=True,
            cwd=PROJECT_DIR,
        )
        assert result.returncode == 0
        data = json.loads((out_dir / "reconciliation_report.json").read_text())
        # With composite key, location change becomes removal+addition
        assert data["summary"]["removed"] == 1
        assert data["summary"]["added"] == 1

    def test_sort_flag(self, tmp_path):
        """--sort delta should produce a CSV sorted by largest delta first."""
        result = subprocess.run(
            [
                sys.executable, "reconcile.py",
                "--output-dir", str(tmp_path),
                "--allow-errors",
                "--sort", "delta",
            ],
            capture_output=True, text=True, cwd=PROJECT_DIR,
        )
        assert result.returncode == 0
        import csv
        with open(tmp_path / "reconciliation_summary.csv") as f:
            rows = list(csv.DictReader(f))
        deltas = [abs(int(r["quantity_delta"])) for r in rows if r["quantity_delta"]]
        assert deltas == sorted(deltas, reverse=True)

    def test_filter_flag(self, tmp_path):
        """--filter changed should only include changed items in CSV."""
        result = subprocess.run(
            [
                sys.executable, "reconcile.py",
                "--output-dir", str(tmp_path),
                "--allow-errors",
                "--filter", "changed",
            ],
            capture_output=True, text=True, cwd=PROJECT_DIR,
        )
        assert result.returncode == 0
        import csv
        with open(tmp_path / "reconciliation_summary.csv") as f:
            rows = list(csv.DictReader(f))
        assert len(rows) > 0
        assert all(r["status"] == "changed" for r in rows)

    def test_tolerance_flag(self, tmp_path):
        """--tolerance should classify small deltas as within_tolerance."""
        snap1 = tmp_path / "s1.csv"
        snap2 = tmp_path / "s2.csv"
        snap1.write_text("sku,name,quantity,location,last_counted\nSKU-001,A,100,WA,2024-01-08\n")
        snap2.write_text("sku,product_name,qty,warehouse,updated_at\nSKU-001,A,98,WA,2024-01-15\n")

        out_dir = tmp_path / "out"
        result = subprocess.run(
            [
                sys.executable, "reconcile.py",
                "--snapshot1", str(snap1),
                "--snapshot2", str(snap2),
                "--output-dir", str(out_dir),
                "--tolerance", "5",
            ],
            capture_output=True, text=True, cwd=PROJECT_DIR,
        )
        assert result.returncode == 0
        report = json.loads((out_dir / "reconciliation_report.json").read_text())
        assert report["summary"]["within_tolerance"] == 1
        assert report["summary"]["changed"] == 0

    def test_key_mode_flag(self, tmp_path):
        """--key-mode sku_location should use composite key."""
        snap1 = tmp_path / "s1.csv"
        snap2 = tmp_path / "s2.csv"
        snap1.write_text(
            "sku,name,quantity,location,last_counted\n"
            "SKU-001,A,100,WA,2024-01-08\n"
            "SKU-002,B,50,WB,2024-01-08\n"
        )
        snap2.write_text(
            "sku,product_name,qty,warehouse,updated_at\n"
            "SKU-001,A,90,WA,2024-01-15\n"
            "SKU-002,B,55,WB,2024-01-15\n"
        )

        out_dir = tmp_path / "out"
        result = subprocess.run(
            [
                sys.executable, "reconcile.py",
                "--snapshot1", str(snap1),
                "--snapshot2", str(snap2),
                "--output-dir", str(out_dir),
                "--key-mode", "sku_location",
            ],
            capture_output=True, text=True, cwd=PROJECT_DIR,
        )
        assert result.returncode == 0
        report = json.loads((out_dir / "reconciliation_report.json").read_text())
        assert report["summary"]["changed"] == 2
