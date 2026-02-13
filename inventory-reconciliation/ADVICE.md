# Project Manager Advice — Inventory Reconciliation

_Review date: Fri Feb 13, 2026 | 201 tests passing | Commit: fa30671_

## Executive Summary

The inventory reconciliation system is **feature-complete and well-tested**. It implements a five-stage modular pipeline (load, normalize, validate, reconcile, report) with 201 passing unit/integration tests across 12+ test files. The codebase demonstrates strong engineering fundamentals: type-safe dataclass models, configurable normalization via YAML, comprehensive quality issue tracking, and production-grade features like fuzzy name matching, composite key support, tolerance bands, and health scoring.

**Overall readiness: 9/10 for a take-home assessment submission.**

The remaining gaps are operational polish items that would matter in a production deployment but are appropriate trade-offs for the scope of this assessment.

## Post-Hardening Review (PM Perspective)

While the engineering work is excellent, a few "product" and "operational" gaps remain that could confuse a new user or limit future scalability.

### 1. Documentation UX
- **Issue**: We currently have `README.md` (the original task instructions) and `PROJECT-README.md` (the actual manual). A user landing on the repo sees the *problem statement* first, not the *solution*.
- **Recommendation**: Add a "Solution & Usage" section to the top of `README.md` that links to `PROJECT-README.md`, or merge the critical "How to Run" instructions into the main README. Don't bury the lead.

### 2. Packaging & Distribution
- **Issue**: The project is a collection of Python scripts. There is no `pyproject.toml`, `setup.py`, or `requirements.txt` visible in the root (although `requirements.txt` exists, is it up to date?).
- **Recommendation**:
    - Add a `pyproject.toml` to define dependencies and build metadata.
    - Consider a `Dockerfile` for containerized execution, which solves the "it works on my machine" problem entirely.

### 3. CI/CD & Automation
- **Issue**: Tests are run manually.
- **Recommendation**: Add a `.github/workflows/test.yml` file to run `pytest` on every push. This is a low-effort, high-value signal of professional engineering practices.

### 4. Data Hygiene
- **Issue**: Test artifacts (`output/`, `.coverage`) are polluting the root directory.
- **Recommendation**: Verify `.gitignore` exists and covers these. (Note: The previous advice mentioned adding `.gitignore`, verify if this was done).

### 5. Future Scalability (Business Logic)
- **Issue**: The current system loads everything into memory (pandas).
- **Recommendation (Future)**:
    - **Polars**: For 1M+ rows, migrating to Polars would offer significant speedups with a similar API.
    - **Database Sync**: Real-world reconciliation often writes to a DB table (e.g., `inventory_audit_log`) rather than just a JSON file.

### 6. Auditability
- **Issue**: We log to stdout.
- **Recommendation**: In a real system, we'd want structured logging sent to an aggregator (Datadog/Splunk). The current `json` log format option is a good start, but ensure it captures *context* (run ID, user ID) for traceability.

## Action Plan

1.  **Docs**: Add a link in `README.md` to `PROJECT-README.md`.
2.  **Git**: Ensure `.gitignore` is present.
3.  **CI**: Create a simple GitHub Actions workflow.