# ADVICE

_Last review: Fri Feb 13 16:44 CST 2026_

## Data pipeline robustness
- **Missing SKU handling** – `normalize_sku` calls `.strip()` without guarding against `None`/`NaN`, so any blank SKU blows up before we can emit a `missing_value` issue (reconciliation/normalizer.py:13-24). Add a safe path (e.g., coerce falsy inputs to `""`) and let the validator report the error.
- **Decimal/invalid quantities** – quantities are truncated via `int(float(...))`, and later the reconciler blindly casts each quantity to `int` (reconciliation/normalizer.py:27-36, reconciliation/reconciler.py:55-113). Result: real fractional counts silently lose precision while malformed strings surface as `TypeError` during reconciliation. Treat non-integer data as hard errors (flag during normalization and skip/abort during reconciliation) instead of truncating.
- **Dates and locations never validated** – `normalize_date` returns `None` for unparseable strings but no quality issue is created, and `find_null_fields` omits the `date`/`location` columns entirely (reconciliation/normalizer.py:39-52, reconciliation/validator.py:56-66). Anything from `"13/40/2024"` to blank warehouses flows downstream unnoticed. Record a `date_format` issue whenever parsing fails and extend the validator to cover all required fields.
- **Severity not enforced** – Even when `validate_snapshot` flags `severity="error"`, the CLI just prints counts and proceeds to generate reports with the bad rows (reconcile.py:65-96). At minimum, fail fast or drop/skip rows tied to error-level issues so negative quantities or missing keys don’t contaminate the reconciliation output.
- **Column order instability** – `load_snapshot` slices columns with `list(required_columns)` where the source is a set (reconciliation/loader.py:43-53). Because set ordering is arbitrary, downstream DataFrames can have columns shuffled run-to-run, which makes diffs, schema validation, and report comparisons noisy. Preserve a deterministic order (e.g., `['sku','name','quantity','location','date']`).

## Testing & quality gates
- **Missing assertion** – `test_total_items_reconciled` documents the expected `summary['total_snapshot_2']` value but never asserts it, so a regression could slip through unnoticed (tests/test_integration.py:117-125). Add the assertion and ensure the math in the comment matches actual reconciled counts.
- **CLI not exercised** – Integration tests call the module-level functions directly; the `reconcile.py` entry point (argument parsing, console output, directory creation) is untested. Add a subprocess/cli test to catch regressions in argument parsing and the reporting workflow.

## Cleanup / follow-ups
- Remove unused imports like `sys` in `reconcile.py` (reconcile.py:10-18) and trim the unused `enumerate` variables in the normalizer to keep lint noise down.
- Next review checkpoint: revisit after fixes/commits land or by 17:00 CST to ensure the above risks are addressed and no new regressions were introduced.
