# Engineering Advice — Inventory Reconciliation (Codex)

## 1. Broaden CLI Test Coverage
- Add end-to-end tests that exercise `--sort`, `--filter`, tolerance flags, and composite-key mode via subprocess to prevent regressions in those code paths.

## 2. Performance Benchmarking
- Establish a baseline (e.g., 100k-row snapshots) and document throughput/memory usage; consider introducing configurable chunked processing or Polars if large datasets become common.

## 3. ABC / Cycle-Count Features
- Implement ABC tagging and cycle-count scheduling hooks so the reconciliation output can directly inform warehouse prioritization—currently only mentioned in ADVICE backlog.

## 4. Master Data Enrichment
- Integrate optional master-data lookups (UoM, pack size, preferred warehouses) so the reconciliation can detect unit mismatches or transfers that quantity deltas alone can’t explain.

## 5. Advanced Audit Logging
- Emit structured logs to disk (JSONL) or support external log sinks; include metadata like user/environment alongside the existing `run_id` for multi-tenant traceability.

## 6. Packaging & Distribution
- Publish the package to PyPI and push the Docker image to a registry to streamline adoption; document versioning strategy.

## 7. Backlog Tracking
- Convert ADVICE items into tracked issues or a `TODO.md` so contributors can pick them up without wading through narrative logs.

---

# Claude's Advice — Honest Review

_204 tests passing. Clean architecture. Here's what I'd fix._

---

## 1. The reconciler assumes normalization always succeeds

`reconciler.py:137` does `int(row['quantity'])` with no guard. If normalization set quantity to `None` or left it as a non-numeric string, this crashes with no useful error message. Same pattern at lines 148, 157.

**Fix**: Assert before coercing, or guard with a default:
```python
qty_raw = row["quantity"]
if qty_raw is None or qty_raw == "":
    # skip or flag — don't crash
    continue
qty1 = int(qty_raw)
```

This is the single most likely production failure.

---

## 2. Windows Excel CSVs will break the loader

Excel on Windows exports UTF-8 with a BOM (`\xef\xbb\xbf`). The first column becomes `"\ufeffsku"` instead of `"sku"`, and the column alias lookup fails silently — no match, no error, just a missing column.

**Fix** in `loader.py`:
```python
pd.read_csv(path, dtype=str, keep_default_na=False, encoding="utf-8-sig")
```

One-line change, prevents a real-world class of failures.

---

## 3. Default CLI behavior fails on the provided sample data

Running `python reconcile.py` with no flags exits with code 1 because the sample data has error-level quality issues. A first-time user clones the repo, runs the tool, and gets an error. The "happy path" requires `--allow-errors`.

**Options**:
- Make `--allow-errors` the default, add `--strict` for fail-fast behavior
- Or add a prominent note in the CLI `--help` epilog and README "Quick Start"

---

## 4. Fuzzy matching doesn't scale

`fuzz.ratio()` at `reconciler.py:184` computes Levenshtein distance for every name-changed item. This is O(m*n) per pair where m, n are string lengths. For 10k changed items with long product names, this becomes a bottleneck.

**Fix**: Only compute similarity when names actually differ (already done), but also consider:
- Caching results for repeated name pairs
- Using `rapidfuzz` instead of `thefuzz` (10-50x faster, drop-in replacement)

---

## 5. `_key` column pollutes the DataFrame

`reconciler.py:99-100` adds a `_key` column to both DataFrames. This is a side effect — callers don't expect their DataFrames modified. The `.copy()` on lines 97-98 mitigates this, but it doubles memory usage for large datasets.

**Better approach**: Build a dict mapping key → row index, avoid modifying the DataFrame at all:
```python
keys_1 = {_build_key_for_row(row, key_mode): idx for idx, row in df1.iterrows()}
```

Or use `pd.merge()` which handles key matching natively.

---

## 6. Custom deep-copy/merge in config.py is unnecessary

`config.py` implements `_deep_copy_dict()` and `_deep_merge()` manually. Python's `copy.deepcopy()` does the same thing, is battle-tested, and handles edge cases (circular references, custom objects) that the custom version doesn't.

```python
import copy
config = copy.deepcopy(DEFAULT_CONFIG)
```

---

## 7. Priority thresholds are magic numbers

`reconciler.py:48-52` hardcodes `10%` and `5%` as priority boundaries. These aren't configurable and aren't documented as constants. If a warehouse wants different thresholds, they have to edit source code.

**Fix**: Add to config.yaml:
```yaml
priority:
  high_threshold_pct: 10
  medium_threshold_pct: 5
```

---

## 8. Validator uses row-by-row iteration

`validator.py` uses patterns like iterating over DataFrames to find negatives and nulls. For large datasets this is slow compared to vectorized pandas operations.

**Example** — instead of building issues row by row for negatives:
```python
neg_mask = pd.to_numeric(df["quantity"], errors="coerce") < 0
for _, row in df[neg_mask].iterrows():
    issues.append(QualityIssue(...))
```

This filters first (vectorized), then only iterates the small number of bad rows.

---

## 9. Date format support is too narrow

The normalizer handles `YYYY-MM-DD` and `MM/DD/YYYY`. Real warehouse exports also use:
- `DD-Mon-YYYY` (e.g., `15-Jan-2024`)
- `YYYY/MM/DD`
- Timestamps (`2024-01-15 14:30:00`)
- `Mon DD, YYYY` (e.g., `Jan 15, 2024`)

The config system supports adding formats, but the defaults only cover two. Adding 3-4 more common formats to `config.default.yaml` would prevent failures on real data without any code changes.

---

## 10. Tests check implementation, not behavior

Several tests assert specific internal values rather than observable behavior:

- `test_similar_names_high_score` asserts `> 0.7` — this tests the threshold, not that the system correctly identifies similar names. A better test: give it "Widget Pro" and "Widget Professional", assert the item is classified as `changed` with `name_changed=True`.
- `test_health_in_json_report` just checks `"health" in data` — doesn't verify the values are sensible (accuracy between 0-100, variance non-negative).
- `test_csv_sort_by_delta` checks only the first two rows — ties and edge cases aren't covered.

**Principle**: Test the contract (what the function promises), not the implementation (how it does it).

---

## 11. No test for the actual sample data end-to-end

There's no test that runs the full pipeline on `data/snapshot_1.csv` and `data/snapshot_2.csv` and asserts specific reconciliation results. The integration tests use synthetic fixtures. If someone changes the normalizer and it silently drops a row from the real data, no test catches it.

**Add**: A regression test that loads the actual CSVs and asserts known output counts (5 added, 2 removed, 70 changed, 2 unchanged, 1 skipped).

---

## 12. `to_flat_dict()` writes `None` as string in CSV

`ItemChange.to_flat_dict()` returns `None` for fields like `old_name` when there's no name change. `csv.DictWriter` writes this as the literal string `"None"` in the CSV. Consumers parsing the CSV will see `"None"` instead of an empty cell.

**Fix**:
```python
def to_flat_dict(self) -> dict:
    return {k: ("" if v is None else v) for k, v in {
        "sku": self.sku,
        ...
    }.items()}
```

---

## 13. Reporter imports tested as private

`reporter.py` defines `_apply_filters()` with an underscore prefix (private), but `test_reporter.py` imports and tests it directly. Either:
- Drop the underscore — it's part of the module's contract
- Or test it indirectly through `generate_csv_report()`

---

## 14. Missing `.gitignore` entry for `.DS_Store`

macOS creates `.DS_Store` files in every directory. The `.gitignore` covers `__pycache__/` and `output/` but not `.DS_Store`. Minor but visible in PRs.

---

## 15. `reconciliation/models.py` `run_id` default is empty string

`ReconciliationResult.run_id` defaults to `""` (line 117). This means if someone creates a result without the CLI (e.g., in tests or as a library), the JSON report gets `"run_id": ""`. Better to default to `None` and omit it from output when not set.

---

## Summary — What I'd prioritize

| Priority | Item | Why |
|----------|------|-----|
| **Now** | Guard `int()` coercion in reconciler (#1) | Production crash |
| **Now** | UTF-8 BOM handling (#2) | Real-world data failure |
| **Now** | Regression test on actual sample data (#11) | Safety net |
| **Soon** | Fix CSV None output (#12) | Downstream consumers break |
| **Soon** | Switch to rapidfuzz (#4) | Free performance win |
| **Soon** | Add more date formats (#9) | Common integration failure |
| **Later** | Configurable priority thresholds (#7) | Extensibility |
| **Later** | Vectorize validator (#8) | Scale |
| **Later** | Replace custom deepcopy (#6) | Code cleanliness |

---

# Engineering Improvement Advice

## 1. Modern Python Packaging & Tooling
The project currently relies on `requirements.txt` and manual script invocation. Modernizing this would improve developer experience and reproducibility.

- **Adopt `pyproject.toml`**: Move from `requirements.txt` to a standard `pyproject.toml`. This consolidates build configuration, dependencies, and tool settings (pytest, ruff, mypy) in one place.
- **Dependency Management**: Consider using **Poetry** or **uv** for lockfile management. This ensures every developer uses the exact same package versions, preventing "it works on my machine" issues.
- **Task Runner**: Add a `Makefile` or `Justfile`. Instead of typing `python reconcile.py ...` or lengthy `pytest` commands, developers could run `make test`, `make lint`, or `make run`.

## 2. Static Analysis & Code Quality
While the code is well-structured, enforcing standards via tooling prevents regression.

- **Linting & Formatting**: Integrate **Ruff**. It's an extremely fast linter and formatter that replaces Flake8, Black, and isort.
- **Type Checking**: Add **mypy** (in strict mode). While type hints exist in the code, they aren't currently enforced. This will catch subtle type-related bugs (e.g., `Optional` handling) before runtime.
- **Pre-commit Hooks**: Set up `pre-commit` to run linting, formatting, and type checking automatically before every git commit.

## 3. Testing Strategy Enhancements
Test coverage is high (201 tests), but the *types* of tests can be expanded.

- **Property-Based Testing**: Use **Hypothesis**. Instead of hardcoding edge cases (like in `test_hardening.py`), Hypothesis generates thousands of random inputs (integers, strings, unicode) to find edge cases you didn't think of.
- **Snapshot Testing**: Use `pytest-snapshot` or `syrupy` for the report generation tests. Instead of manually asserting JSON keys, you compare the output against a saved "golden" file.
- **Mutation Testing**: Use **mutmut**. This modifies your code (e.g., changes `if a > 0` to `if a >= 0`) and runs your tests. If tests still pass, it means your tests aren't strict enough.

## 4. Scalability & Performance
The current implementation uses Pandas, which loads all data into memory.

- **Lazy Loading / Streaming**: For massive datasets (millions of rows), switch to **Polars** or Pandas chunking. Polars is generally faster and memory-efficient for this type of columnar data processing.
- **Database Integration**: Instead of reading/writing CSVs, consider integrating with SQLite or PostgreSQL to store historical reconciliation data. This enables trend analysis ("Is SKU-123 always off by 5?") over time.

## 5. DevOps & CI/CD
Automation is currently manual.

- **GitHub Actions**: Add a workflow (`.github/workflows/ci.yml`) to:
    1.  Install dependencies.
    2.  Run linting/formatting checks.
    3.  Run the full test suite.
    4.  (Optional) Build a Docker image.
- **Docker**: The `Dockerfile` exists but should be optimized (multi-stage builds) to keep the image size small.

## 6. Documentation Clarity
- **Single Source of Truth**: The split between `README.md` (instructions) and `PROJECT-README.md` (documentation) is confusing. Merge them. The `README.md` should contain the "What is this?" and "How do I run it?" sections at the very top.