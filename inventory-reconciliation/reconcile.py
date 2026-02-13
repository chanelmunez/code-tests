#!/usr/bin/env python3
"""Inventory Reconciliation — compare two warehouse snapshots and report changes.

Usage:
    python reconcile.py
    python reconcile.py --snapshot1 data/snapshot_1.csv --snapshot2 data/snapshot_2.csv
    python reconcile.py --output-dir output/
"""

import argparse
import sys
from pathlib import Path

from reconciliation.loader import load_snapshot
from reconciliation.normalizer import normalize_dataframe
from reconciliation.validator import validate_snapshot
from reconciliation.reconciler import reconcile
from reconciliation.reporter import generate_json_report, generate_csv_report


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Reconcile two inventory snapshots and generate a change report."
    )
    parser.add_argument(
        "--snapshot1",
        default="data/snapshot_1.csv",
        help="Path to the first (older) snapshot CSV (default: data/snapshot_1.csv)",
    )
    parser.add_argument(
        "--snapshot2",
        default="data/snapshot_2.csv",
        help="Path to the second (newer) snapshot CSV (default: data/snapshot_2.csv)",
    )
    parser.add_argument(
        "--output-dir",
        default="output",
        help="Directory for output files (default: output/)",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    snap1_path = Path(args.snapshot1)
    snap2_path = Path(args.snapshot2)
    output_dir = Path(args.output_dir)

    # --- Load ---
    print(f"Loading {snap1_path} ...")
    df1 = load_snapshot(snap1_path)
    print(f"  {len(df1)} rows loaded.")

    print(f"Loading {snap2_path} ...")
    df2 = load_snapshot(snap2_path)
    print(f"  {len(df2)} rows loaded.")

    # --- Normalize ---
    print("Normalizing data ...")
    df1, issues_1 = normalize_dataframe(df1, "snapshot_1")
    df2, issues_2 = normalize_dataframe(df2, "snapshot_2")
    all_issues = issues_1 + issues_2
    print(f"  {len(all_issues)} normalization issues found.")

    # --- Validate ---
    print("Validating data quality ...")
    all_issues.extend(validate_snapshot(df1, "snapshot_1"))
    all_issues.extend(validate_snapshot(df2, "snapshot_2"))
    error_count = sum(1 for i in all_issues if i.severity == "error")
    warning_count = len(all_issues) - error_count
    print(f"  {error_count} errors, {warning_count} warnings.")

    # --- Reconcile ---
    print("Reconciling snapshots ...")
    result = reconcile(df1, df2, quality_issues=all_issues)

    # --- Report ---
    json_path = output_dir / "reconciliation_report.json"
    csv_path = output_dir / "reconciliation_summary.csv"

    generate_json_report(result, json_path, snap1_path, snap2_path)
    generate_csv_report(result, csv_path)

    # --- Summary ---
    summary = result.summary
    print("\n" + "=" * 50)
    print("RECONCILIATION SUMMARY")
    print("=" * 50)
    print(f"  Snapshot 1 items (reconciled): {summary['total_snapshot_1']}")
    print(f"  Snapshot 2 items (reconciled): {summary['total_snapshot_2']}")
    print(f"  Added (new in snapshot 2):     {summary['added']}")
    print(f"  Removed (only in snapshot 1):  {summary['removed']}")
    print(f"  Changed:                       {summary['changed']}")
    print(f"  Unchanged:                     {summary['unchanged']}")
    print(f"  Skipped (duplicate SKUs):      {summary['skipped_due_to_duplicates']}")
    print(f"  Data quality issues:           {summary['quality_issues']}")
    print("=" * 50)

    if result.skipped_skus:
        print(f"\n  Skipped SKUs: {', '.join(result.skipped_skus)}")

    print(f"\nReports written to:")
    print(f"  JSON: {json_path}")
    print(f"  CSV:  {csv_path}")


if __name__ == "__main__":
    main()
