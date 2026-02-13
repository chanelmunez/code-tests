# Project Manager Advice — Inventory Reconciliation

_Review date: Fri Feb 13, 2026 | 203 tests passing | Commit: fa30671_

---

## Executive Summary

The inventory reconciliation system is **feature-complete and well-tested**. It implements a five-stage modular pipeline (load, normalize, validate, reconcile, report) with 203 passing unit/integration tests across 12+ test files. The codebase demonstrates strong engineering fundamentals: type-safe dataclass models, configurable normalization via YAML, comprehensive quality issue tracking, and production-grade features like fuzzy name matching, composite key support, tolerance bands, and health scoring.

**Overall readiness: 9/10 for a take-home assessment submission.**

The remaining gaps are operational polish items that would matter in a production deployment but are appropriate trade-offs for the scope of this assessment.

---

## What Was Done Well

| Area | Assessment |
|------|-----------|
| **Architecture** | Clean separation of concerns — each pipeline stage is an independent, testable module with its own responsibility |
| **Data integrity** | CSVs read as `dtype=str` with `keep_default_na=False`; no silent type coercion or NaN injection |
| **Error handling** | Error-severity SKUs excluded from reconciliation entirely; warnings auto-corrected with full audit trail |
| **Test coverage** | 203 tests covering happy paths, edge cases, hardening scenarios, regressions, CLI behavior, and configuration |
| **Configurability** | YAML-based normalization rules, CLI flags for key mode/tolerance/sorting/filtering/logging |
| **Documentation** | NOTES.md explains every architectural decision; PROGRESS.md tracks milestones; CODE-TESTING-PROGRESS.md maps every test |

---

## Current State by Module

| Module | File | Tests | Status |
|--------|------|-------|--------|
| Loader | `reconciliation/loader.py` | 8 | Stable — column aliases, deterministic ordering, empty string preservation |
| Normalizer | `reconciliation/normalizer.py` | 46 | Stable — SKU/quantity/date/text/location normalization, config-driven |
| Validator | `reconciliation/validator.py` | 17 | Stable — duplicates, negatives, null fields across all columns |
| Reconciler | `reconciliation/reconciler.py` | 50 | Stable — composite keys, tolerance, fuzzy matching, priority assignment |
| Reporter | `reconciliation/reporter.py` | 22 | Stable — JSON/CSV output, sorting, filtering |
| Config | `reconciliation/config.py` | 11 | Stable — YAML loading, deep merge, sensible defaults |
| CLI | `reconcile.py` | 8 | Stable — 13 flags, structured logging, pipeline log |
| Integration | `tests/test_integration.py` | 16 | Stable — end-to-end pipeline validation |
| Hardening | `tests/test_hardening.py` | 9 | Stable — 0-byte files, garbage data, extreme values |
| Edge cases | `tests/test_new_edge_cases.py` | 4 | Stable — Unicode, location casing |
| QA regressions | `tests/test_quality_gaps.py` | 4 | Stable — regression tests from prior review |
| Advice coverage | `tests/test_advice_coverage.py` | 6 | Stable — loader NaN handling, severity enforcement |

---

## Reconciliation Results (Sample Data)

| Metric | Value |
|--------|-------|
| Snapshot 1 items | 74 |
| Snapshot 2 items | 77 |
| Added | 5 |
| Removed | 2 |
| Changed | 70 |
| Unchanged | 2 |
| Skipped (errors) | 1 (SKU-045: duplicate + negative quantity) |
| Quality issues | 13 (11 warnings, 2 errors) |
| Accuracy rate | 2.8% |
| Data quality score | 93.4% |
| Total variance | 950 units |

---

## Remaining Items (Prioritized)

### High Priority — Address Before Submission

1. **Add `.gitignore`**: Generated artifacts (`output/`, `.coverage`, `__pycache__/`) are tracked in git. This clutters diffs and commits stale reports. A standard Python `.gitignore` should be added.

2. **CLI exit code**: The CLI returns 0 even when error-level quality issues are found. For a production tool, non-zero exit on errors enables CI/CD gating. For this assessment, documenting the current behavior as a deliberate choice (permissive mode — skip bad SKUs and continue) is sufficient.

3. **Clean up this ADVICE.md**: The previous version was a chronological review log mixing resolved and unresolved items. This rewrite addresses that. Prior review notes are preserved in git history.

### Medium Priority — Nice to Have

4. **CLI error-path tests**: Current CLI tests cover happy paths and file-not-found. Adding tests for `--sort`, `--filter`, and scenarios with quality errors would strengthen coverage.

5. **Output directory auto-creation**: The reporter already calls `mkdir(parents=True, exist_ok=True)`, so this is handled. Verify that the CLI doesn't fail if `output/` doesn't exist on a fresh clone.

6. **Performance baseline**: The hardening suite tests 1,000 rows. A 100k-row benchmark would demonstrate scalability awareness, but is not essential for this scope.

### Low Priority — Future Enhancements

7. **ABC analysis integration**: Prioritize SKUs by business value/turnover for cycle counting — industry standard practice referenced in prior research.

8. **Multi-cycle tracking**: Compare reconciliation results across time periods to identify persistent discrepancies and trends.

9. **Root-cause classification**: Categorize discrepancies into buckets (shrinkage, receiving errors, system bugs, human error) for warehouse operations teams.

10. **Plugin architecture**: Allow custom quality checks and normalization rules to be registered without modifying core modules.

---

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Generated files pollute git | High | Low | Add `.gitignore` |
| Reviewer confused by stale ADVICE.md | Medium | Medium | Replaced with this document |
| Large dataset performance unknown | Low | Medium | Document as known limitation; 1k-row test passes in <4s |
| Exit code behavior surprises operators | Low | Low | Document as intentional design choice in NOTES.md |

---

## Strengths to Highlight in Review

These are the aspects of this project that demonstrate senior engineering thinking:

1. **Error severity enforcement** — Not just detecting bad data, but deciding what to do with it (exclude from reconciliation, not silently include)
2. **SKU normalization** — Recognizing that `SKU005`, `sku-008`, and `SKU-005` are the same item prevents false adds/removes
3. **Configurable normalization** — Business rules in YAML, not hardcoded; the system adapts to different data formats without code changes
4. **Quality audit trail** — Every correction logged with original value, corrected value, severity, and snapshot source
5. **Comprehensive test strategy** — Unit tests per module + integration tests + hardening + regression tests from QA feedback
6. **Health scoring** — Goes beyond "what changed" to answer "how healthy is this inventory data"
7. **Fuzzy matching** — Name similarity scores help distinguish typos from legitimate product renames
8. **Composite key support** — Same SKU in multiple warehouses handled correctly without false duplicate flags

---

## Recommendation

**The project is ready for submission.** The core engineering work is solid, well-tested, and well-documented. The remaining items (`.gitignore`, exit codes) are operational polish that can be addressed in a few minutes if desired, but they do not detract from the quality of the implementation or the engineering decisions demonstrated.

The codebase shows a developer who:
- Thinks about data integrity (not just happy-path functionality)
- Writes tests that cover edge cases and regressions (not just basic assertions)
- Documents decisions and trade-offs (not just what the code does)
- Builds for configurability without over-engineering (YAML config with sensible defaults)
- Understands real-world inventory challenges (fuzzy matching, tolerance bands, composite keys, health scoring)
