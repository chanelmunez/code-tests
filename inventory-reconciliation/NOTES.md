# Notes — Claude

## Approach

I treated this as a data pipeline problem, not a scripting exercise. The solution is a five-stage pipeline — load, normalize, validate, reconcile, report — where each stage has a single responsibility and its own tests. This makes it possible to swap out the loader for a database reader or change the output format without touching reconciliation logic. The pipeline reads all CSV values as strings (`dtype=str`) and converts explicitly, because letting pandas guess types silently turns empty strings into `NaN` and integer quantities into floats.

## Key Decisions

**Exclude dirty rows rather than guess.** SKU-045 appears twice in snapshot 2 with contradictory data (qty 23 in Warehouse A vs qty -5 in Warehouse B). Merging or averaging these would produce a number that exists in neither source. Instead, the pipeline drops all rows with error-level issues from reconciliation and flags them separately, so the report only contains data you can trust. Warnings (whitespace, float-stored integers, date format) are auto-corrected.

**Normalize SKUs before matching.** Three SKUs differ only in formatting between snapshots (`SKU005`, `sku-008`, `SKU018`). Without canonicalizing these to `SKU-NNN`, they'd wrongly show up as both "removed" and "added." The normalizer uppercases, inserts hyphens, and zero-pads — all configurable via YAML if the SKU scheme changes.

**Default to fail-fast; opt in to leniency.** The CLI exits non-zero when errors are detected unless you pass `--allow-errors`. This is the safer default for an automated context — a cron job shouldn't silently produce a partial report.

## Data Quality Issues

| Issue | Severity | Detail |
|---|---|---|
| Duplicate SKU | Error | SKU-045 appears twice in snapshot 2 with conflicting names and quantities |
| Negative quantity | Error | SKU-045 row has qty `-5` |
| Inconsistent SKU format | Warning | `SKU005`, `sku-008`, `SKU018` — missing hyphens, wrong case |
| Whitespace in names | Warning | Leading/trailing spaces on 5 product names (e.g., ` Widget B`, `Cable Ties 100pk `) |
| Float quantities | Warning | `70.0` and `80.00` stored as floats; safely truncated to integers |
| Mixed date formats | Warning | One row uses `01/15/2024` instead of `2024-01-15` |
| Schema mismatch | Info | Column headers differ between snapshots (`name`/`product_name`, `quantity`/`qty`, `location`/`warehouse`, `last_counted`/`updated_at`) |
