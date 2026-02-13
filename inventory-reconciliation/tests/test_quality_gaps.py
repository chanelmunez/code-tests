"""Regression tests derived from advisory findings."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pandas as pd

from reconciliation.normalizer import normalize_dataframe

PROJECT_DIR = Path(__file__).parent.parent


def test_normalize_dataframe_handles_blank_sku_reports_issue():
    """Blank SKUs should not crash normalization and must be flagged as quality issues."""
    df = pd.DataFrame({
        "sku": [None],
        "name": ["Widget"],
        "quantity": ["10"],
        "location": ["Warehouse A"],
        "date": ["2024-01-01"],
    })
    normalized, issues = normalize_dataframe(df, "snapshot_test")
    assert normalized.loc[0, "sku"] == ""
    assert any(i.issue_type == "sku_format" for i in issues)


def test_normalize_dataframe_reports_invalid_quantity_issue():
    df = pd.DataFrame({
        "sku": ["SKU-101"],
        "name": ["Gizmo"],
        "quantity": ["not-a-number"],
        "location": ["Warehouse A"],
        "date": ["2024-01-01"],
    })
    _, issues = normalize_dataframe(df, "snapshot_test")
    assert any(i.issue_type == "invalid_quantity" for i in issues)


def test_normalize_dataframe_reports_invalid_date_issue():
    df = pd.DataFrame({
        "sku": ["SKU-102"],
        "name": ["Widget"],
        "quantity": ["10"],
        "location": ["Warehouse A"],
        "date": ["13/40/2024"],
    })
    _, issues = normalize_dataframe(df, "snapshot_test")
    assert any(i.issue_type == "invalid_date" for i in issues)


def test_cli_reports_duplicate_skus(tmp_path):
    """When duplicates exist, the CLI should surface them in the summary output."""
    snap1 = tmp_path / "snapshot1.csv"
    snap2 = tmp_path / "snapshot2.csv"

    snap1.write_text(
        "sku,name,quantity,location,last_counted\n" "SKU-001,A,5,Warehouse A,2024-01-01\n"
    )
    snap2.write_text(
        "sku,name,quantity,location,last_counted\n"
        "SKU-001,A,5,Warehouse A,2024-01-08\n"
        "SKU-001,A,10,Warehouse B,2024-01-08\n"
    )

    result = subprocess.run(
        [
            sys.executable,
            "reconcile.py",
            "--snapshot1",
            str(snap1),
            "--snapshot2",
            str(snap2),
            "--output-dir",
            str(tmp_path / "out"),
        ],
        cwd=PROJECT_DIR,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    output = result.stdout + result.stderr
    assert "Skipped SKUs" in output
    assert "SKU-001" in output
