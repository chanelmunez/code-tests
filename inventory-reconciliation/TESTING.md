# Testing & QA Status

_Last updated: 2026-02-13_

## Overview

The project ships with a pytest suite that exercises the entire pipeline—from CSV ingestion through reporting—plus CLI subprocess tests and regression suites distilled from ongoing reviews.

```
pytest  # 203 passed in ~4.1s on Python 3.12
```

## Coverage Highlights

| Area | Files / Tests |
|------|---------------|
| Loaders & Normalizers | `tests/test_loader.py`, `tests/test_normalizer.py` |
| Validators & Reconcilers | `tests/test_validator.py`, `tests/test_reconciler.py` |
| Reporters | `tests/test_reporter.py` |
| CLI / End-to-End | `tests/test_cli.py`, `tests/test_integration.py` |
| Hardening / Edge Cases | `tests/test_hardening.py`, `tests/test_new_edge_cases.py` |
| Advice Regression Suites | `tests/test_advice_coverage.py`, `tests/test_quality_gaps.py` |
| Configuration | `tests/test_config.py` |

## Recent Additions

- **Regression cases** (2026-02-13): Added `tests/test_quality_gaps.py` to lock in behavior around blank SKUs, invalid quantities/dates, and duplicate-SKU reporting.
- **Integration assertion**: `tests/test_integration.py` now verifies `summary['total_snapshot_2']` matches the number of reconciled SKUs.
- **CLI logging coverage**: `tests/test_cli.py` checks both text and JSON log formats and validates the `pipeline_log` embedded in the JSON output.

## Known Gaps

| Gap | Impact | Planned Action |
|-----|--------|----------------|
| Multi-warehouse / ABC cycle-count strategies untested | Limits confidence for future feature work | Add design + tests once feature work begins |

## How to Run

1. Install dependencies via `pip install -r requirements.txt` (use a virtualenv).
2. From repo root, run `pytest` to execute the full suite.
3. Use `pytest -k <pattern>` for focused runs (e.g., `pytest -k cli`).
4. CLI-specific smoke test: `python reconcile.py --output-dir tmp/out` (ensures reports are generated end-to-end).

## Tooling

- **pytest** with builtin fixtures plus `tmp_path` for isolated CLI runs.
- **pandas** for creating in-memory DataFrames during normalization/validation tests.
- **subprocess** module in tests to run `reconcile.py` the way a user would.
- **CI**: `.github/workflows/tests.yml` runs `pytest` on every push/PR using Python 3.12.

Maintain this document as the authoritative source for QA scope, recent changes, and remaining test gaps.
