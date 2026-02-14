# Inventory Reconciliation - Notes

## Key Decisions

*   **Modular Architecture**: I structured the solution into five distinct stages: Load, Normalize, Validate, Reconcile, and Report. This separation of concerns made testing each component (200+ tests) straightforward and allows for future extensibility (e.g., adding a database loader or a new report format).
*   **Safe Data Ingestion**: I used `keep_default_na=False` and `dtype=str` when loading CSVs. This prevents Pandas from silently converting empty strings to `NaN` floats, which causes type errors downstream. I also enforced `utf-8-sig` encoding to handle Excel-generated CSVs with BOM correctly.
*   **Strict Error Handling**: I adopted a "fail-safe" approach for reconciliation. SKUs with error-level data quality issues (duplicates, negative quantities, unparseable values) are **excluded** from the reconciliation report to prevent data contamination. Warnings (like whitespace) are auto-corrected.
*   **Normalization Strategy**: Instead of hardcoding rules, I implemented a configurable normalization system. This handles SKU standardization (e.g., `SKU005` -> `SKU-005`), Unicode cleanup (NFKC), and location casing.
*   **Smart Matching**: I implemented fuzzy matching (Levenshtein distance) to detect potential product renames vs. new items, and added support for composite keys (SKU + Location) to handle multi-warehouse scenarios.

## Data Quality Issues Found

During development and testing with the provided snapshots, the pipeline identified:

1.  **Duplicate SKU**: `SKU-045` appeared twice in Snapshot 2 with conflicting data (one valid, one with negative quantity).
2.  **Negative Quantity**: `SKU-045` had a quantity of `-5`.
3.  **Inconsistent Formatting**: Several SKUs lacked hyphens (`SKU005`, `sku-008`), locations had casing variances, and product names contained trailing whitespace.
4.  **Date Formats**: Mixed date formats (`YYYY-MM-DD` vs `MM/DD/YYYY`) were detected and normalized to ISO 8601.
5.  **Numeric Issues**: Quantities were stored as floats (`70.0`) in some records.

## Approach

1.  **Exploration**: I started by analyzing the CSV schema and identified the mismatched headers (`qty` vs `quantity`) immediately.
2.  **Core Logic**: I implemented the `reconcile` function first to define the data structures (`ItemChange`, `ReconciliationResult`).
3.  **Hardening**: I wrote a dedicated hardening test suite (`tests/test_hardening.py`) to verify behavior against 0-byte files, binary garbage, and extreme integer values.
4.  **Refinement**: Based on code review, I added robust guards against `None` values in the normalization layer and ensured deterministic column ordering in the output to prevent flaky tests.
5.  **Documentation**: I separated the solution manual (`PROJECT-README.md`) from the assessment brief to keep the entry point clean.
