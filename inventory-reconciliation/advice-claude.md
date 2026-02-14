# Combined Advice — All Sources, Prioritized Top to Bottom

_Sources: Claude review, Gemini review, PM review. Deduplicated, ordered by impact._

---

## Critical — Production crash / data corruption risks

### 1. Reconciler assumes normalization always succeeds

`reconciler.py:137` does `int(row['quantity'])` with no guard. If normalization left quantity as `None` or a non-numeric string, this crashes with no useful error. Same at lines 148, 157.

```python
qty_raw = row["quantity"]
if qty_raw is None or qty_raw == "":
    continue  # skip or flag — don't crash
qty1 = int(qty_raw)
```

### 2. Windows Excel CSVs break the loader

Excel on Windows exports UTF-8 with a BOM (`\xef\xbb\xbf`). The first column becomes `"\ufeffsku"` instead of `"sku"`, and the column alias lookup fails silently.

```python
# loader.py — one-line fix:
pd.read_csv(path, dtype=str, keep_default_na=False, encoding="utf-8-sig")
```

### 3. `to_flat_dict()` writes `None` as literal string in CSV

`ItemChange.to_flat_dict()` returns `None` for fields like `old_name`. `csv.DictWriter` writes this as the string `"None"`. Downstream consumers parsing the CSV see `"None"` instead of an empty cell.

```python
def to_flat_dict(self) -> dict:
    d = {"sku": self.sku, "status": self.status, ...}
    return {k: ("" if v is None else v) for k, v in d.items()}
```

---

## High — Real-world robustness

### 4. Default CLI fails on the provided sample data

Running `python reconcile.py` with no flags exits with code 1 because the sample data has error-level issues. A first-time user clones, runs, gets an error. The happy path requires `--allow-errors`.

- **Option A**: Make `--allow-errors` the default, add `--strict` for fail-fast
- **Option B**: Add a prominent note in `--help` epilog and README Quick Start

### 5. Date format support is too narrow

The normalizer handles `YYYY-MM-DD` and `MM/DD/YYYY`. Real warehouse exports also produce:
- `15-Jan-2024` (spreadsheet export)
- `YYYY/MM/DD` (slashes)
- `2024-01-15 14:30:00` (timestamps)
- `Jan 15, 2024` (US English)

The config system supports adding formats, but the defaults only cover two. Add 3-4 more to `config.default.yaml`.

### 6. No regression test against actual sample data

No test runs the full pipeline on `data/snapshot_1.csv` and `data/snapshot_2.csv` asserting specific output counts (5 added, 2 removed, 70 changed, 2 unchanged, 1 skipped). Integration tests use synthetic fixtures only. A normalizer change that silently drops a row would go undetected.

### 7. Priority thresholds are magic numbers

`reconciler.py:48-52` hardcodes `10%` and `5%` as priority boundaries. Not configurable, not named as constants. A warehouse wanting different thresholds must edit source code.

```yaml
# Add to config.yaml:
priority:
  high_threshold_pct: 10
  medium_threshold_pct: 5
```

---

## Medium — Testing strategy

### 8. Tests check implementation, not behavior

- `test_similar_names_high_score` asserts `> 0.7` — tests the threshold, not that similar names are correctly classified as `changed` with `name_changed=True`
- `test_health_in_json_report` checks `"health" in data` but doesn't verify values are sensible (accuracy 0-100, variance non-negative)
- `test_csv_sort_by_delta` checks only the first two rows — ties not covered

**Principle**: Test the contract (what the function promises), not the implementation.

### 9. CLI end-to-end tests don't cover advanced flags

Tests exercise the happy path and file-not-found, but never run `--sort`, `--filter`, `--tolerance`, or `--key-mode` via subprocess. Regressions in flag parsing would go unnoticed.

### 10. Property-based testing with Hypothesis

Instead of hardcoding edge cases in `test_hardening.py`, Hypothesis generates thousands of random inputs (integers, strings, unicode) to find cases you didn't think of. Particularly valuable for the normalizer.

### 11. Snapshot / golden-file testing for reports

Use `pytest-snapshot` or `syrupy` for report tests. Instead of manually asserting JSON keys, compare output against a saved golden file. Catches regressions in report structure automatically.

### 12. Mutation testing with mutmut

Mutmut modifies your code (e.g., changes `>` to `>=`) and re-runs tests. If tests still pass, they aren't strict enough. Reveals assertions that look good but don't actually catch bugs.

---

## Medium — Code quality & architecture

### 13. Fuzzy matching doesn't scale

`fuzz.ratio()` is O(m*n) per string pair. For 10k changed items with long product names, this becomes a bottleneck. `rapidfuzz` is a drop-in replacement that's 10-50x faster.

### 14. `_key` column pollutes the DataFrame

`reconciler.py:99-100` adds `_key` to both DataFrames. The `.copy()` on lines 97-98 prevents caller side effects but doubles memory. Better: use a dict mapping key to row index, or use `pd.merge()`.

### 15. Validator uses row-by-row iteration

`validator.py` iterates to find negatives and nulls. Vectorize first, then iterate only the bad rows:

```python
neg_mask = pd.to_numeric(df["quantity"], errors="coerce") < 0
for _, row in df[neg_mask].iterrows():
    issues.append(QualityIssue(...))
```

### 16. Custom deep-copy/merge in config.py is unnecessary

`_deep_copy_dict()` and `_deep_merge()` reimplement `copy.deepcopy()`. The stdlib version is battle-tested and handles edge cases the custom version doesn't.

### 17. Reporter's `_apply_filters()` is private but tested directly

`reporter.py` defines `_apply_filters()` with underscore prefix, but `test_reporter.py` imports and tests it. Either drop the underscore (it's part of the contract) or test it indirectly through `generate_csv_report()`.

### 18. `run_id` defaults to empty string

`ReconciliationResult.run_id` defaults to `""`. Library users who don't use the CLI get `"run_id": ""` in JSON output. Default to `None` and omit from output when not set.

---

## Medium — Tooling & DevOps

### 19. Static analysis: Ruff + mypy + pre-commit

- **Ruff**: Extremely fast linter/formatter replacing Flake8 + Black + isort
- **mypy (strict mode)**: Type hints exist but aren't enforced. Catches `Optional` handling bugs before runtime
- **pre-commit hooks**: Run linting, formatting, and type checking automatically before every commit

### 20. Task runner (Makefile or Justfile)

Instead of typing `python reconcile.py ...` or `pytest` commands, developers run `make test`, `make lint`, `make run`. Low effort, high usability.

### 21. Docker multi-stage builds

The `Dockerfile` exists but uses a single stage. A multi-stage build (builder → runtime) cuts the image size significantly by excluding dev dependencies and build tools.

### 22. `.DS_Store` missing from `.gitignore`

macOS creates `.DS_Store` in every directory. Minor but visible in PRs.

---

## Lower — Performance & scale

### 23. Performance baseline needed

The hardening suite tests 1k rows. A 100k-row benchmark with documented throughput would demonstrate scalability awareness. No SLO targets exist.

### 24. Consider Polars for large datasets

For 1M+ rows, Polars offers significant speedups over pandas with a similar API. The current architecture (load → normalize → validate → reconcile → report) would port cleanly.

### 25. Database integration for historical tracking

Instead of just diffing two CSVs, writing reconciliation results to a database (SQLite/PostgreSQL) enables trend analysis: "Is SKU-123 always off by 5?" and persistent audit trails.

---

## Lower — Documentation & UX

### 26. README split confuses newcomers

`README.md` is the assessment brief. `PROJECT-README.md` is the actual manual. A user landing on the repo sees the problem statement first, not the solution. Add a "Solution & Usage" link at the top of `README.md`, or merge the key instructions.

### 27. CLI help text lacks examples

`argparse` has no epilog or examples. Users must read NOTES.md to understand `--tolerance` vs `--tolerance-pct` or what `--key-mode sku_location` does.

### 28. Config schema undocumented

`config.default.yaml` exists but there's no documentation of what fields are available, their types, or their effects. Users writing custom configs are guessing.

---

## Future — Feature ideas (not blocking)

### 29. ABC cycle-count prioritization

Prioritize SKUs by business value/turnover for counting frequency. Industry standard; referenced in prior research.

### 30. Root-cause classification

Categorize discrepancies into buckets (shrinkage, receiving errors, system bugs, human error) for operations teams.

### 31. Plugin architecture for custom rules

Allow custom quality checks and normalization rules to be registered without modifying core modules. Useful when different warehouses have different business logic.

### 32. Multi-cycle tracking

Compare reconciliation results across time periods to identify persistent discrepancies and trends rather than just point-in-time diffs.

### 33. Structured logging to aggregator

The `--log-format json` option is a start. Production systems would pipe these to Datadog/Splunk with context (run ID, user ID, warehouse ID) for traceability.

---

## Summary

| # | Item | Priority | Category |
|---|------|----------|----------|
| 1 | Guard `int()` coercion in reconciler | **Critical** | Bug |
| 2 | UTF-8 BOM handling | **Critical** | Bug |
| 3 | CSV writes `None` as string | **Critical** | Bug |
| 4 | Default CLI fails on sample data | High | UX |
| 5 | More date formats in defaults | High | Robustness |
| 6 | Regression test on real data | High | Testing |
| 7 | Configurable priority thresholds | High | Extensibility |
| 8 | Test contracts, not implementation | Medium | Testing |
| 9 | CLI tests for advanced flags | Medium | Testing |
| 10 | Property-based testing (Hypothesis) | Medium | Testing |
| 11 | Snapshot testing for reports | Medium | Testing |
| 12 | Mutation testing (mutmut) | Medium | Testing |
| 13 | Switch to rapidfuzz | Medium | Performance |
| 14 | Remove `_key` column side effect | Medium | Code quality |
| 15 | Vectorize validator | Medium | Performance |
| 16 | Use stdlib deepcopy | Medium | Code quality |
| 17 | Fix private function testing | Medium | Code quality |
| 18 | `run_id` default to None | Medium | Code quality |
| 19 | Ruff + mypy + pre-commit | Medium | Tooling |
| 20 | Makefile / Justfile | Medium | Tooling |
| 21 | Docker multi-stage build | Medium | Tooling |
| 22 | .DS_Store in .gitignore | Medium | Hygiene |
| 23 | 100k-row performance baseline | Lower | Performance |
| 24 | Polars migration path | Lower | Performance |
| 25 | Database integration | Lower | Architecture |
| 26 | Fix README split | Lower | Docs |
| 27 | CLI help examples | Lower | Docs |
| 28 | Config schema docs | Lower | Docs |
| 29-33 | Future features (ABC, root-cause, plugins, multi-cycle, logging) | Future | Features |
