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
├── test_loader.py
├── test_normalizer.py
├── test_validator.py
├── test_reconciler.py
├── test_reporter.py
├── test_integration.py
└── test_cli.py           # CLI end-to-end tests (added in phase 2)
```

## Pipeline Flow

```
Load CSVs → Normalize columns → Clean data → Validate → Reconcile → Report
                                                              ↓
                                              Error-level SKUs excluded
```

## Phase 1: Implementation

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

## Phase 2: Hardening (from ADVICE.md, TESTING.md, CODE-TESTING-PROGRESS.md)

- [x] Guard `normalize_sku` and `normalize_date` against None/NaN inputs
- [x] Reject fractional quantities (70.5 → error) vs. integer-as-float (70.0 → warning)
- [x] Emit error-level issue for unparseable dates
- [x] Extend validator to check all 5 required fields (added date, location)
- [x] Enforce severity: exclude error-level SKUs from reconciliation output
- [x] Fix column order determinism (set → fixed list)
- [x] Remove unused `sys` import and `enumerate` idx variables
- [x] Add missing assertion in `test_total_items_reconciled`
- [x] Add CLI end-to-end tests (6 tests via subprocess)
- [x] Add normalization collision edge case tests
- [x] Add hardening test suite (`tests/test_hardening.py`) for edge cases (0-byte, garbage, extreme values)
- [x] Generate edge-case test datasets (`generate_test_data.py`)
- [x] Update NOTES.md with severity enforcement + SKU-per-location limitation

## Phase 3: Advice & Feedback Implementation

- [x] Loader: `keep_default_na=False` to prevent NaN injection
- [x] Normalizer: Robust guards for None/NaN inputs
- [x] Severity: Strict exclusion of error-level SKUs from reconciliation
- [x] Validation: Empty string vs NaN testing (`tests/test_advice_coverage.py`)
- [x] Advanced Normalization: NFKC Unicode normalization
- [x] Advanced Normalization: Location Title Casing

## Test Results

```
149 passed in 2.53s
```

**Test breakdown:**
- `test_loader.py` — 8 tests
- `test_normalizer.py` — 30+ tests
- `test_validator.py` — 13 tests
- `test_reconciler.py` — 19 tests
- `test_reporter.py` — 15 tests
- `test_integration.py` — 16 tests
- `test_cli.py` — 6 tests
- `test_hardening.py` — 9 tests
- `test_new_edge_cases.py` — 4 tests
- `test_advice_coverage.py` — 6 tests

## Reconciliation Results

| Metric | Count |
|--------|-------|
| Snapshot 1 items (reconciled) | 74 |
| Snapshot 2 items (reconciled) | 77 |
| Added (new in snapshot 2) | 5 |
| Removed (only in snapshot 1) | 2 |
| Changed | 70 |
| Unchanged | 2 |
| Skipped (data quality errors) | 1 |
| Data quality issues | 13 |
