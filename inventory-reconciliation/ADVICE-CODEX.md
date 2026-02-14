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
