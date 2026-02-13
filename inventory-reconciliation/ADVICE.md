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

---

_Follow-up review: Fri Feb 13 16:55 CST 2026_

## Documentation gaps
- **README is still the assessment brief** – `README.md:1-51` repeats the recruiter instructions but never documents *this* implementation (setup, dependency install, how to run `reconcile.py`, where reports/tests land, expected outputs). Replace or extend it with a project README that covers usage and troubleshooting so future maintainers don't have to reverse-engineer the workflow.
- **NOTES omit current limitations** – `NOTES.md:5-27` highlights architecture decisions but skips the unresolved risks we already identified (e.g., normalization crashes on blank SKUs, date/location issues flow downstream, severity errors don’t block reconciliation). Call these out explicitly so reviewers know what still needs hardening.
- **Progress log lacks open items** – `PROGRESS.md:50-90` marks every checkbox complete and lists final metrics, yet we still have outstanding QA work (missing assertions, CLI gaps, data-validation bugs). Add a "Next steps" / "Known issues" section so the document reflects reality and keeps the backlog visible.

---

_Follow-up review: Fri Feb 13 17:03 CST 2026_

## CSV ingestion & normalization
- **pandas still injects NaNs** – `pd.read_csv(..., dtype=str)` (reconciliation/loader.py:35-41) continues to convert blank cells/"NA" tokens into actual `NaN` objects. When those flow into `normalize_sku`/`normalize_date`, the code calls `.strip()` on a float and raises `AttributeError` before any data-quality issue can be emitted. Set `keep_default_na=False` (or `na_filter=False`) during load so you always receive literal strings and can intentionally decide how to treat blanks.
- **Invalid quantities/dates slip through silently** – `normalize_quantity` and `normalize_date` return `None` when parsing fails (reconciliation/normalizer.py:27-52), but `normalize_dataframe` never records an issue or substitutes a safe default in that case; downstream, `reconcile` still does `int(row['quantity'])` and crashes (reconciliation/reconciler.py:55-113). Emit explicit `QualityIssue`s for "invalid_quantity" / "invalid_date" and either drop those SKUs or guard the reconciler so it never attempts to coerce `None`.

## Repo hygiene
- **Derived artifacts tracked** – `output/reconciliation_report.json` shows up as modified every run because the generated timestamp (reconciliation/reportor.py:11-41) makes the file nondeterministic. These reports—and the `.coverage` file—should live in `.gitignore` so reviewers focus on source diffs instead of churn from regenerated artifacts. Until that’s in place, it’s very easy to accidentally commit stale reports.

---

_Follow-up review: Fri Feb 13 17:05 CST 2026_

## Test coverage observations
- **Regression gap for null SKUs/quantities** – Even the hardening fixtures never feed blank SKUs or `NaN` quantities through the pipeline, so the `.strip()` crash path in `normalize_sku`/`normalize_quantity` is untested (see `tests/test_normalizer.py:97-134` and `tests/test_hardening.py:10-111`). Add fixtures with empty `sku`/`quantity`/`date` cells and assert that normalization records the right `QualityIssue` and that reconciliation skips them instead of raising.
- **Integration test still missing assertion** – `tests/test_integration.py:117-125` documents the expected `summary['total_snapshot_2']` value but never asserts it, so the suite cannot catch regressions in reconciled counts.
- **CLI failure paths unverified** – `tests/test_cli.py:15-66` exercises happy paths and a nonexistent file, but we never assert that quality errors (e.g., duplicate SKUs) cause a non-zero exit or that stderr surfaces actionable messaging. Add a test that feeds a bad snapshot and ensures the CLI either aborts (if we choose that behavior) or clearly reports skipped SKUs.
- **Generated artifacts clutter diffs** – The CLI tests run `reconcile.py` in place and regenerate `output/reconciliation_report.json`, which shows up as a working-tree change after every `pytest`. Either mock the output dir (as other tests already do) or ensure the suite cleans the default `output/` directory so local diffs stay clean.

_Test run: 139 passed in 2.13s (pytest)._ 

---

_Follow-up review: Fri Feb 13 17:17 CST 2026 (industry research)_

## External practices worth adopting
- **Structured reconciliation workflow** – ShipBob’s 5-step process (physical count → compare books → audit shipments since last count → document/resolve root causes → reconcile on a cadence) plus its three scheduling strategies (seasonal counts, ABC-by-value focus, and fixed/randomized spot checks) highlight the importance of prioritizing SKUs by business impact and backtracking movements between cycles before altering the ledger (source: ShipBob, “Inventory Reconciliation: How to Reconcile Your Inventory in 5 Steps,” Nov 19 2025). Our pipeline currently just diffs two CSVs and reports deltas; we should capture shipment deltas between snapshots, store investigation notes, and let users select reconciliation modes (seasonal runs vs. ABC-prioritized subsets vs. ad-hoc spot checks) to mirror real warehouses.
- **Cycle counting patterns** – Industry guidance on cycle counting (Wikipedia “Cycle count”) emphasizes Pareto/ABC, usage-based, statistical, and location-sweep strategies plus 6S prerequisites (segregate scrap, enforce labeling, restrict access). Embedding these concepts in tooling means: tagging SKUs with ABC tiers, allowing frequency configuration by usage/value, surfacing “location drift” as a quality issue, and ensuring our validator can flag unsegregated scrap rows or multi-location mismatches.
- **Root-cause catalogs** – Intuendi’s 2025 write-up (“Inventory Reconciliation: What It Is, Why It’s Crucial & 5-Step Process”) calls out the major discrepancy buckets (human/process error, shrinkage, supplier receiving mistakes, system/unit-of-measure bugs) and ties reconciliation to financial accuracy, demand planning, and fraud detection. Our reporting should classify issues by these categories, surface shrinkage signals (e.g., persistent negative deltas) separately, and integrate receiving/return logs so supplier-caused count errors can be isolated.
- **Data normalization discipline** – Data cleansing guidance (Wikipedia “Data cleansing”) frames normalization as harmonizing file formats, enforcing data types/ranges, and appending reference data. For this project, that translates to:  
  * capturing strict schema constraints (types, ranges) during load instead of best-effort coercion,  
  * augmenting SKUs with reference master data (e.g., canonical unit of measure, standard pack sizes) before comparison, and  
  * logging every normalization action (typo fix, abbreviation expansion) so downstream auditors see exactly why a field changed.
- **Tooling expectations from WMS vendors** – ShipBob positions intelligent cycle counts, automatic safety-stock alerts, and distributed inventory views as table stakes for reconciliation accuracy. To stay competitive, expose metrics like service-level impact (stockouts avoided), add safety-stock calculations tied to normalized demand, and offer hooks for multi-warehouse comparisons rather than assuming single-site CSVs.
