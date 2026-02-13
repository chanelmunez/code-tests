# Notes — Inventory Reconciliation

## Approach

I built a modular pipeline that processes the snapshots in four stages: **load → normalize → validate → reconcile**. Each stage is a separate module with its own unit tests, making the logic easy to verify and extend.

The loader standardizes the different column names between files (`name`/`product_name`, `quantity`/`qty`, etc.) into a common schema. The normalizer then cleans the raw data — fixing SKU formats, stripping whitespace, converting float quantities to integers, and normalizing date formats — while logging every correction as a quality issue. The validator runs semantic checks (duplicates, negative quantities, missing values across all fields). Finally, the reconciler joins the two clean datasets on SKU to classify each item as added, removed, changed, or unchanged.

## Key Decisions

- **Error severity enforcement**: Any SKU associated with an error-level quality issue (duplicate, negative quantity, fractional quantity, unparseable date, missing field) is excluded from reconciliation entirely. This prevents bad data from contaminating the output. Warnings (whitespace, float-stored integers, non-standard dates) are auto-corrected and the item proceeds normally.
- **Duplicate SKU handling**: SKU-045 appears twice in snapshot_2 with conflicting data (different names, quantities, and locations). Rather than guess which row is correct, I excluded it from reconciliation entirely and flagged it prominently in the quality issues report.
- **Fractional quantities rejected**: A value like `70.5` is treated as an error (inventory counts should be whole numbers), while `70.0` is safely converted to `70` with a warning. This prevents silent precision loss from `int(float(...))` truncation.
- **SKU normalization**: SKUs like `SKU005`, `sku-008`, and `SKU018` are normalized to `SKU-NNN` format (uppercase, hyphenated, zero-padded). Without this, these items would incorrectly appear as "removed" from one snapshot and "added" to the other. A side-effect is that `SKU005` and `SKU-005` in the same file become a duplicate after normalization — this is by design and is flagged.
- **Change tracking scope**: Beyond quantity deltas, the tool also detects product name changes and warehouse/location changes, since these could indicate data entry errors or legitimate transfers.
- **All data read as strings**: CSVs are loaded with `dtype=str` to prevent pandas from silently coercing types. Conversion happens explicitly in the normalizer.

## Known Limitations

- **Single SKU per location**: The system uses SKU as the sole primary key. If the same SKU legitimately exists in multiple warehouses within a single snapshot, it is flagged as a duplicate and excluded. A real-world extension would use (SKU, location) as a composite key.

## Data Quality Issues Found

| Severity | Issue | Count | Examples |
|----------|-------|-------|----------|
| Warning | Whitespace in product names | 5 | ` Widget B`, `Cable Ties 100pk `, ` HDMI Cable 3ft ` |
| Warning | SKU format inconsistency | 3 | `SKU005`, `sku-008`, `SKU018` |
| Warning | Float quantities | 2 | `70.0`, `80.00` |
| Warning | Non-standard date format | 1 | `01/15/2024` instead of `2024-01-15` |
| Error | Duplicate SKU | 1 | SKU-045 appears twice with conflicting data |
| Error | Negative quantity | 1 | SKU-045 has qty `-5` |

Additionally, the two snapshots use completely different column naming conventions, which the loader handles transparently.

## Known Limitations / Next Steps

- **Severity handling**: The CLI currently finishes successfully even when error-level quality issues are detected. We need a policy decision (fail fast vs. continue with warnings) and matching implementation/tests.
- **Date/location validation**: `find_null_fields` only covers `sku`, `name`, and `quantity`. Extend validation so empty dates/locations are surfaced before reconciliation.
- **Generated artefacts**: Running the CLI writes to `output/` and leaves those files tracked unless the user overrides `--output-dir`. Consider ignoring output artefacts or defaulting to a temp directory for tests.
- **Master data enrichment**: The data model assumes SKUs are self-contained. Looking up canonical metadata (UoM, pack sizes, preferred warehouse) would let us detect more subtle discrepancies such as unit-mismatch changes.
