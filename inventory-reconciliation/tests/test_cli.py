"""Tests for the CLI entry point (reconcile.py)."""

import json
import subprocess
import sys
from pathlib import Path

import pytest


PROJECT_DIR = Path(__file__).parent.parent


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
