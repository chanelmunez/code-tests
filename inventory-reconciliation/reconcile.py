#!/usr/bin/env python3
"""Inventory Reconciliation — compare two warehouse snapshots and report changes.

Usage:
    python reconcile.py
    python reconcile.py --snapshot1 data/snapshot_1.csv --snapshot2 data/snapshot_2.csv
    python reconcile.py --output-dir output/
    python reconcile.py --log-format json
"""

import argparse
import json
import logging
from pathlib import Path

from reconciliation.config import load_config
from reconciliation.loader import load_snapshot
from reconciliation.normalizer import normalize_dataframe
from reconciliation.validator import validate_snapshot
from reconciliation.reconciler import reconcile
from reconciliation.reporter import generate_json_report, generate_csv_report

logger = logging.getLogger("reconciliation")


def _setup_logging(log_format: str = "text", log_level: str = "INFO") -> None:
    """Configure the reconciliation logger."""
    level = getattr(logging, log_level.upper(), logging.INFO)
    handler = logging.StreamHandler()
    if log_format == "json":
        handler.setFormatter(logging.Formatter("%(message)s"))
    else:
        handler.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(handler)
    logger.setLevel(level)


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
    parser.add_argument(
        "--log-format",
        choices=["text", "json"],
        default="text",
        help="Log output format (default: text)",
    )
    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        default="INFO",
        help="Logging level (default: INFO)",
    )
    parser.add_argument(
        "--key-mode",
        choices=["sku", "sku_location"],
        default="sku",
        help="Reconciliation key: 'sku' (default) or 'sku_location' for composite key",
    )
    parser.add_argument(
        "--tolerance",
        type=int,
        default=0,
        help="Absolute tolerance: ignore quantity deltas <= this value (default: 0)",
    )
    parser.add_argument(
        "--tolerance-pct",
        type=float,
        default=0.0,
        help="Percentage tolerance: ignore quantity deltas <= this %% of old quantity (default: 0)",
    )
    parser.add_argument(
        "--config",
        default=None,
        help="Path to YAML normalization config file (default: built-in defaults)",
    )
    parser.add_argument(
        "--sort",
        choices=["sku", "status", "delta", "priority"],
        default=None,
        help="Sort CSV output by: sku, status, delta (largest first), or priority",
    )
    parser.add_argument(
        "--filter",
        dest="filter_status",
        choices=["added", "removed", "changed", "unchanged", "within_tolerance"],
        default=None,
        help="Filter CSV output to only show items with this status",
    )
    parser.add_argument(
        "--allow-errors",
        action="store_true",
        help=(
            "Continue and write reports even if error-level data quality issues are found "
            "(default: fail fast)."
        ),
    )
    return parser.parse_args(argv)


def _log(
    message: str,
    log_format: str = "text",
    *,
    level: int = logging.INFO,
    **kwargs,
) -> None:
    """Log a message, optionally as JSON."""
    payload = {"message": message, **kwargs}
    if log_format == "json":
        logger.log(level, json.dumps(payload))
    else:
        logger.log(level, message)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    _setup_logging(args.log_format, args.log_level)

    snap1_path = Path(args.snapshot1)
    snap2_path = Path(args.snapshot2)
    output_dir = Path(args.output_dir)
    norm_config = load_config(args.config)
    pipeline_log: list[dict] = []

    # --- Load ---
    _log(f"Loading {snap1_path} ...", args.log_format, stage="load", file=str(snap1_path))
    df1 = load_snapshot(snap1_path)
    _log(f"  {len(df1)} rows loaded.", args.log_format, stage="load", rows=len(df1))

    _log(f"Loading {snap2_path} ...", args.log_format, stage="load", file=str(snap2_path))
    df2 = load_snapshot(snap2_path)
    _log(f"  {len(df2)} rows loaded.", args.log_format, stage="load", rows=len(df2))

    pipeline_log.append({
        "stage": "load",
        "snapshot_1_rows": len(df1),
        "snapshot_2_rows": len(df2),
    })

    # --- Normalize ---
    _log("Normalizing data ...", args.log_format, stage="normalize")
    df1, issues_1 = normalize_dataframe(df1, "snapshot_1", config=norm_config)
    df2, issues_2 = normalize_dataframe(df2, "snapshot_2", config=norm_config)
    all_issues = issues_1 + issues_2
    _log(
        f"  {len(all_issues)} normalization issues found ({len(issues_1)} snap1, {len(issues_2)} snap2).",
        args.log_format, stage="normalize", total=len(all_issues),
        snap1_issues=len(issues_1), snap2_issues=len(issues_2),
    )

    pipeline_log.append({
        "stage": "normalize",
        "issues_snapshot_1": len(issues_1),
        "issues_snapshot_2": len(issues_2),
        "total_issues": len(all_issues),
    })

    # --- Validate ---
    _log("Validating data quality ...", args.log_format, stage="validate")
    val_issues_1 = validate_snapshot(df1, "snapshot_1")
    val_issues_2 = validate_snapshot(df2, "snapshot_2")
    all_issues.extend(val_issues_1)
    all_issues.extend(val_issues_2)
    error_count = sum(1 for i in all_issues if i.severity == "error")
    warning_count = len(all_issues) - error_count
    _log(
        f"  {error_count} errors, {warning_count} warnings.",
        args.log_format, stage="validate", errors=error_count, warnings=warning_count,
    )

    pipeline_log.append({
        "stage": "validate",
        "validation_issues_snapshot_1": len(val_issues_1),
        "validation_issues_snapshot_2": len(val_issues_2),
        "total_errors": error_count,
        "total_warnings": warning_count,
    })

    if error_count > 0 and not args.allow_errors:
        error_issues = [issue for issue in all_issues if issue.severity == "error"]
        _log(
            "Error-level data quality issues detected. Aborting before reconciliation. "
            "Re-run with --allow-errors to produce reports anyway.",
            args.log_format,
            stage="validate",
            level=logging.ERROR,
            errors=error_count,
        )
        for issue in error_issues[:5]:
            _log(
                f"  [{issue.sku}] {issue.issue_type}: {issue.detail}",
                args.log_format,
                stage="validate",
                level=logging.ERROR,
            )
        remaining = len(error_issues) - 5
        if remaining > 0:
            _log(
                f"  ... {remaining} additional error issues omitted",
                args.log_format,
                stage="validate",
                level=logging.ERROR,
            )
        raise SystemExit(1)

    # --- Reconcile ---
    _log("Reconciling snapshots ...", args.log_format, stage="reconcile")
    result = reconcile(
        df1, df2,
        quality_issues=all_issues,
        key_mode=args.key_mode,
        tolerance=args.tolerance,
        tolerance_pct=args.tolerance_pct,
    )
    result.pipeline_log = pipeline_log

    pipeline_log.append({
        "stage": "reconcile",
        "added": len(result.added),
        "removed": len(result.removed),
        "changed": len(result.changed),
        "unchanged": len(result.unchanged),
        "skipped": len(result.skipped_skus),
    })

    # --- Report ---
    json_path = output_dir / "reconciliation_report.json"
    csv_path = output_dir / "reconciliation_summary.csv"

    generate_json_report(result, json_path, snap1_path, snap2_path)
    generate_csv_report(
        result, csv_path, sort_by=args.sort, filter_status=args.filter_status,
    )

    pipeline_log.append({"stage": "report", "json": str(json_path), "csv": str(csv_path)})

    # --- Summary ---
    summary = result.summary
    _log("\n" + "=" * 50, args.log_format)
    _log("RECONCILIATION SUMMARY", args.log_format, stage="summary")
    _log("=" * 50, args.log_format)
    _log(f"  Snapshot 1 items (reconciled): {summary['total_snapshot_1']}", args.log_format)
    _log(f"  Snapshot 2 items (reconciled): {summary['total_snapshot_2']}", args.log_format)
    _log(f"  Added (new in snapshot 2):     {summary['added']}", args.log_format)
    _log(f"  Removed (only in snapshot 1):  {summary['removed']}", args.log_format)
    _log(f"  Changed:                       {summary['changed']}", args.log_format)
    _log(f"  Unchanged:                     {summary['unchanged']}", args.log_format)
    if summary["within_tolerance"] > 0:
        _log(f"  Within tolerance:              {summary['within_tolerance']}", args.log_format)
    _log(f"  Skipped (data quality errors): {summary['skipped_due_to_errors']}", args.log_format)
    _log(f"  Data quality issues:           {summary['quality_issues']}", args.log_format)
    _log("=" * 50, args.log_format)

    # --- Health Score ---
    health = result.health
    _log(f"\n  Inventory accuracy:            {health['accuracy_rate']}%", args.log_format)
    _log(f"  Total variance (abs):          {health['total_variance']} units", args.log_format)
    _log(f"  Data quality score:            {health['data_quality_score']}%", args.log_format)

    if result.skipped_skus:
        _log(f"\n  Skipped SKUs: {', '.join(result.skipped_skus)}", args.log_format)

    _log(f"\nReports written to:", args.log_format)
    _log(f"  JSON: {json_path}", args.log_format)
    _log(f"  CSV:  {csv_path}", args.log_format)


if __name__ == "__main__":
    main()
