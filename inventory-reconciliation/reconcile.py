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
from uuid import uuid4

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
        description="Reconcile two inventory snapshots and generate a change report.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""\
examples:
  python reconcile.py                                    # basic run (fails on errors)
  python reconcile.py --allow-errors                     # continue despite data issues
  python reconcile.py --key-mode sku_location            # composite key (multi-warehouse)
  python reconcile.py --tolerance 5                      # ignore deltas <= 5 units
  python reconcile.py --tolerance-pct 2                  # ignore deltas <= 2%
  python reconcile.py --sort delta --filter changed      # sort by largest delta, only changes
  python reconcile.py --config custom.yaml               # custom normalization rules
  python reconcile.py --log-format json                  # structured JSON logging
""",
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
    run_id = uuid4().hex

    def log(message: str, *, stage: str | None = None, level: int = logging.INFO, **kwargs) -> None:
        context = {"stage": stage} if stage else {}
        context.update(kwargs)
        context["run_id"] = run_id
        _log(message, args.log_format, level=level, **context)

    # --- Load ---
    log(f"Loading {snap1_path} ...", stage="load", file=str(snap1_path))
    df1 = load_snapshot(snap1_path)
    log(f"  {len(df1)} rows loaded.", stage="load", rows=len(df1))

    log(f"Loading {snap2_path} ...", stage="load", file=str(snap2_path))
    df2 = load_snapshot(snap2_path)
    log(f"  {len(df2)} rows loaded.", stage="load", rows=len(df2))

    pipeline_log.append({
        "stage": "load",
        "run_id": run_id,
        "snapshot_1_rows": len(df1),
        "snapshot_2_rows": len(df2),
    })

    # --- Normalize ---
    log("Normalizing data ...", stage="normalize")
    df1, issues_1 = normalize_dataframe(df1, "snapshot_1", config=norm_config)
    df2, issues_2 = normalize_dataframe(df2, "snapshot_2", config=norm_config)
    all_issues = issues_1 + issues_2
    log(
        f"  {len(all_issues)} normalization issues found ({len(issues_1)} snap1, {len(issues_2)} snap2).",
        stage="normalize", total=len(all_issues),
        snap1_issues=len(issues_1), snap2_issues=len(issues_2),
    )

    pipeline_log.append({
        "stage": "normalize",
        "run_id": run_id,
        "issues_snapshot_1": len(issues_1),
        "issues_snapshot_2": len(issues_2),
        "total_issues": len(all_issues),
    })

    # --- Validate ---
    log("Validating data quality ...", stage="validate")
    val_issues_1 = validate_snapshot(df1, "snapshot_1")
    val_issues_2 = validate_snapshot(df2, "snapshot_2")
    all_issues.extend(val_issues_1)
    all_issues.extend(val_issues_2)
    error_count = sum(1 for i in all_issues if i.severity == "error")
    warning_count = len(all_issues) - error_count
    log(
        f"  {error_count} errors, {warning_count} warnings.",
        stage="validate", errors=error_count, warnings=warning_count,
    )

    pipeline_log.append({
        "stage": "validate",
        "run_id": run_id,
        "validation_issues_snapshot_1": len(val_issues_1),
        "validation_issues_snapshot_2": len(val_issues_2),
        "total_errors": error_count,
        "total_warnings": warning_count,
    })

    if error_count > 0 and not args.allow_errors:
        error_issues = [issue for issue in all_issues if issue.severity == "error"]
        log(
            "Error-level data quality issues detected. Aborting before reconciliation. "
            "Re-run with --allow-errors to produce reports anyway.",
            stage="validate",
            level=logging.ERROR,
            errors=error_count,
        )
        for issue in error_issues[:5]:
            log(
                f"  [{issue.sku}] {issue.issue_type}: {issue.detail}",
                stage="validate",
                level=logging.ERROR,
            )
        remaining = len(error_issues) - 5
        if remaining > 0:
            log(
                f"  ... {remaining} additional error issues omitted",
                stage="validate",
                level=logging.ERROR,
            )
        raise SystemExit(1)

    # --- Reconcile ---
    log("Reconciling snapshots ...", stage="reconcile")
    result = reconcile(
        df1, df2,
        quality_issues=all_issues,
        key_mode=args.key_mode,
        tolerance=args.tolerance,
        tolerance_pct=args.tolerance_pct,
    )
    result.run_id = run_id
    result.pipeline_log = pipeline_log

    pipeline_log.append({
        "stage": "reconcile",
        "run_id": run_id,
        "added": len(result.added),
        "removed": len(result.removed),
        "changed": len(result.changed),
        "unchanged": len(result.unchanged),
        "skipped": len(result.skipped_skus),
    })

    # --- Report ---
    json_path = output_dir / "reconciliation_report.json"
    csv_path = output_dir / "reconciliation_summary.csv"

    generate_json_report(result, json_path, snap1_path, snap2_path, run_id=run_id)
    generate_csv_report(
        result, csv_path, sort_by=args.sort, filter_status=args.filter_status,
    )

    pipeline_log.append({
        "stage": "report",
        "run_id": run_id,
        "json": str(json_path),
        "csv": str(csv_path),
    })

    # --- Summary ---
    summary = result.summary
    log("\n" + "=" * 50)
    log("RECONCILIATION SUMMARY", stage="summary")
    log("=" * 50)
    log(f"  Snapshot 1 items (reconciled): {summary['total_snapshot_1']}")
    log(f"  Snapshot 2 items (reconciled): {summary['total_snapshot_2']}")
    log(f"  Added (new in snapshot 2):     {summary['added']}")
    log(f"  Removed (only in snapshot 1):  {summary['removed']}")
    log(f"  Changed:                       {summary['changed']}")
    log(f"  Unchanged:                     {summary['unchanged']}")
    if summary["within_tolerance"] > 0:
        log(f"  Within tolerance:              {summary['within_tolerance']}")
    log(f"  Skipped (data quality errors): {summary['skipped_due_to_errors']}")
    log(f"  Data quality issues:           {summary['quality_issues']}")
    log("=" * 50)

    # --- Health Score ---
    health = result.health
    log(f"\n  Inventory accuracy:            {health['accuracy_rate']}%")
    log(f"  Total variance (abs):          {health['total_variance']} units")
    log(f"  Data quality score:            {health['data_quality_score']}%")

    if result.skipped_skus:
        log(f"\n  Skipped SKUs: {', '.join(result.skipped_skus)}")

    log(f"\nReports written to:")
    log(f"  JSON: {json_path}")
    log(f"  CSV:  {csv_path}")


if __name__ == "__main__":
    main()
