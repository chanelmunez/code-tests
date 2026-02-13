# Progress Log

## Decisions Made (Pre-Implementation)

- **Output format**: Both JSON (full structured report) and CSV (flat reconciliation table)
- **Duplicate handling**: Flag duplicate SKUs and exclude them from reconciliation entirely (data is ambiguous)
- **Change scope**: Track all changes — quantity, product name, and location/warehouse
- **Libraries**: pandas for data manipulation, pytest for testing

## Data Quality Issues Identified

| # | Issue | Location | Detail |
|---|-------|----------|--------|
| 1 | Column name mismatch | Both files | `name`/`product_name`, `quantity`/`qty`, `location`/`warehouse`, `last_counted`/`updated_at` |
| 2 | SKU format inconsistency | snapshot_2 | `SKU005` (missing hyphen), `sku-008` (lowercase), `SKU018` (missing hyphen) |
| 3 | Whitespace in names | Both files | Leading/trailing spaces on product names (e.g., ` Widget B`, ` Compressed Air Can`) |
| 4 | Float quantities | snapshot_2 | `70.0`, `80.00` stored as floats instead of integers |
| 5 | Negative quantity | snapshot_2 | SKU-045 has qty `-5` |
| 6 | Duplicate SKU | snapshot_2 | SKU-045 appears twice: row 44 (qty 23, Warehouse A) and row 54 (qty -5, Warehouse B) |
| 7 | Date format inconsistency | snapshot_2 | `01/15/2024` on line 34 vs `2024-01-15` everywhere else |
| 8 | Product name change | snapshot_2 | SKU-045 "Multimeter Pro" → "Multimeter Professional" |

## Architecture

```
reconcile.py              # CLI entry point
reconciliation/
├── __init__.py
├── models.py             # Dataclasses (QualityIssue, ReconciliationResult)
├── loader.py             # CSV loading + column normalization
├── normalizer.py         # Data cleaning (SKU, whitespace, quantities, dates)
├── validator.py          # Semantic quality checks (negatives, duplicates, nulls)
├── reconciler.py         # Core diff logic (match/add/remove/change)
└── reporter.py           # JSON + CSV report generation
tests/
├── conftest.py           # Shared pytest fixtures
├── test_normalizer.py
├── test_validator.py
├── test_reconciler.py
├── test_reporter.py
└── test_integration.py
```

## Pipeline Flow

```
Load CSVs → Normalize columns → Clean data → Validate → Reconcile → Report
```

## Implementation Progress

- [x] Project scaffolding
- [x] Data models (models.py)
- [x] CSV loader (loader.py)
- [x] Data normalizer (normalizer.py)
- [x] Data validator (validator.py)
- [x] Reconciliation engine (reconciler.py)
- [x] Report generator (reporter.py)
- [x] Main script (reconcile.py)
- [x] Tests — 105 passing
- [x] Run and verify
- [x] NOTES.md
- [x] Git commits

## QA & Hardening

- [x] Edge case analysis
- [x] Hardening test suite (`tests/test_hardening.py`)
- [x] Bug fix: Deterministic column loading
- [ ] CLI End-to-End Verification
- [ ] Final Report Review

## Test Results

```
105 passed in 0.19s
```

**Test breakdown:**
- `test_loader.py` — 8 tests (CSV loading, column mapping, error handling)
- `test_normalizer.py` — 19 tests (SKU/quantity/date normalization, DataFrame cleaning)
- `test_validator.py` — 11 tests (duplicates, negatives, nulls)
- `test_reconciler.py` — 16 tests (add/remove/change/unchanged, duplicates, edge cases)
- `test_reporter.py` — 15 tests (JSON structure, CSV format, file creation)
- `test_integration.py` — 16 tests (full pipeline with real data)

## Reconciliation Results

| Metric | Count |
|--------|-------|
| Snapshot 1 items (reconciled) | 74 |
| Snapshot 2 items (reconciled) | 77 |
| Added (new in snapshot 2) | 5 |
| Removed (only in snapshot 1) | 2 |
| Changed | 70 |
| Unchanged | 2 |
| Skipped (duplicate SKU-045) | 1 |
| Data quality issues | 13 |
