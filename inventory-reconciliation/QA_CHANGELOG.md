# QA & Hardening Changelog

**Date:** 2026-02-13
**Author:** QA Engineer (Session ID: 12437-17283)

## Summary
This session focused on hardening the data ingestion pipeline against edge cases, ensuring robust error handling for malformed data, and implementing feedback from the ADVICE.md review.

## Code Changes

### `reconciliation/loader.py`
- **Fix:** Implemented deterministic column ordering to prevent test flakiness.
- **Fix:** Added `keep_default_na=False` to `pd.read_csv`. This prevents empty CSV cells from being converted to `NaN` floats, ensuring they are treated as empty strings. This fixes a crash where `.strip()` was called on float `NaN`.

### `reconciliation/normalizer.py`
- **Hardening:** Added guards to `normalize_sku` and `normalize_date` to safely handle `None` or `NaN` inputs without crashing.
- **Feature:** Implemented `NFKC` Unicode normalization for text fields. This ensures that equivalent characters (e.g., composed vs. decomposed accents) are treated as identical.
- **Feature:** Added Title Case normalization for the `location` field (e.g., "warehouse a" -> "Warehouse A") to prevent false positive changes.

### `tests/`
- **New Suite:** `tests/test_hardening.py`
    - Covers extreme edge cases: 0-byte files, binary garbage, header-only files, extreme integer values, and SKU collisions.
- **New Suite:** `tests/test_new_edge_cases.py`
    - Verifies Unicode normalization and location casing logic.
- **New Suite:** `tests/test_advice_coverage.py`
    - Verifies specific fixes requested in `ADVICE.md` (loader empty strings, error-level SKU exclusion).
- **Tooling:** `generate_test_data.py`
    - Script to generate the artifacts required for `test_hardening.py`.

## Documentation
- **Created:** `TESTING.md` - Log of QA assessment, plans, and phase outcomes.
- **Created:** `CODE-TESTING-PROGRESS.md` - Detailed test coverage reports.
- **Updated:** `PROGRESS.md` - Tracked project status and completion of Phase 2/3.

## Verified Outcomes
- **Test Coverage:** 149 tests passed (98% coverage).
- **Robustness:** The pipeline now gracefully handles empty files, garbage input, and mixed encodings without crashing.
- **Accuracy:** Error-level quality issues (e.g., negative quantities) now strictly exclude the affected SKUs from the reconciliation report, preventing data contamination.
