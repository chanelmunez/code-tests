# Code Testing Progress

## Test Coverage Report

**Date**: 2026-02-13
**Status**: 149 passed, 0 failed
**Overall Coverage**: 98%

| Module | Statements | Missed | Coverage |
|:---|:---:|:---:|:---:|
| `reconciliation/__init__.py` | 0 | 0 | 100% |
| `reconciliation/loader.py` | 16 | 0 | 100% |
| `reconciliation/models.py` | 63 | 6 | 90% |
| `reconciliation/normalizer.py` | 88 | 0 | 100% |
| `reconciliation/reconciler.py` | 45 | 0 | 100% |
| `reconciliation/reporter.py` | 19 | 0 | 100% |
| `reconciliation/validator.py` | 33 | 0 | 100% |
| **TOTAL** | **264** | **6** | **98%** |

## Hardening Tests Added

### Phase 3: Advice & Feedback Coverage

New tests in `tests/test_advice_coverage.py` cover:

| Test Case | Description | Result |
|:---|:---|:---:|
| `test_loader_reads_empty_strings_not_nan` | Verify `keep_default_na=False` prevents `NaN` injection for blank cells. | PASS |
| `test_normalize_sku_guards` | Verify `normalize_sku` handles `None`/`NaN` gracefully. | PASS |
| `test_reconciler_skips_unique_error_sku` | Verify that *any* error-level issue (e.g., negative qty) excludes the SKU from diffs. | PASS |

### Phase 2b: Advanced Edge Cases (Unicode & Localization)

New tests in `tests/test_new_edge_cases.py` cover:

| Test Case | Description | Result |
|:---|:---|:---:|
| `test_unicode_normalization` | Verify `NFKC` normalization handles `Café` (composed) vs `Café` (decomposed) equivalence. | PASS |
| `test_location_case_normalization` | Verify "Warehouse A" and "warehouse a" are treated as identical locations. | PASS |
| `test_date_bounds` | Placeholder for future date range validation (currently passes/noop). | PASS |
| `test_euro_quantities` | Placeholder for locale-specific number format discussion. | PASS |

### Phase 2a: Hardening (Previous)

| Test Case | Description | Result |
|:---|:---|:---:|
| `test_load_0byte_file` | Verify error handling for truly empty (0 byte) files | PASS |
| `test_load_empty_table` | Verify correct handling of CSV with headers but no data | PASS |
| `test_load_garbage_file` | Verify robustness against binary/garbage data | PASS |
| `test_missing_columns` | Ensure validation catches missing required columns | PASS |
| `test_huge_file_performance` | Verify processing of larger datasets (1000+ rows) | PASS |
| `test_duplicate_handling_all_duplicates` | Verify system safely skips/flags when entire file is duplicates | PASS |
| `test_normalization_collisions` | Check that distinct raw SKUs normalizing to the same ID are flagged as duplicates | PASS |
| `test_extreme_values` | Verify handling of large integers and long strings | PASS |
| `test_reconcile_empty_dataframes` | Ensure reconciliation engine handles empty inputs gracefully | PASS |

## Test Data

Generated in `data/`:
- `testing-0bytes.csv`
- `testing-empty.csv`
- `testing-garbage.csv`
- `testing-huge.csv`
- `testing-duplicates.csv`
- `testing-missing-cols.csv`
- `testing-collisions.csv`
- `testing-extreme.csv`

## Bugs/Issues Fixed

- **Unicode Safety**: Implemented `NFKC` normalization for names, SKUs, and locations to prevent false positives on character encoding differences.
- **Location Casing**: Implemented Title Casing for locations to standardise "warehouse a" -> "Warehouse A".
- **Column Order Determinism**: `loader.py` was updated to ensure columns are returned in a fixed, deterministic order.