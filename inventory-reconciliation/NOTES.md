# Notes — Inventory Reconciliation

## Approach

I built a modular pipeline that processes the snapshots in four stages: **load → normalize → validate → reconcile**. Each stage is a separate module with its own unit tests, making the logic easy to verify and extend.

The loader standardizes the different column names between files (`name`/`product_name`, `quantity`/`qty`, etc.) into a common schema. The normalizer then cleans the raw data — fixing SKU formats, stripping whitespace, converting float quantities to integers, and normalizing date formats — while logging every correction as a quality issue. The validator runs semantic checks (duplicates, negative quantities, missing values). Finally, the reconciler joins the two clean datasets on SKU to classify each item as added, removed, changed, or unchanged.

## Key Decisions

- **Duplicate SKU handling**: SKU-045 appears twice in snapshot_2 with conflicting data (different names, quantities, and locations). Rather than guess which row is correct, I excluded it from reconciliation entirely and flagged it prominently in the quality issues report. This avoids silently propagating bad data.
- **SKU normalization**: SKUs like `SKU005`, `sku-008`, and `SKU018` are normalized to `SKU-NNN` format (uppercase, hyphenated, zero-padded). Without this, these items would incorrectly appear as "removed" from one snapshot and "added" to the other.
- **Change tracking scope**: Beyond quantity deltas, the tool also detects product name changes and warehouse/location changes, since these could indicate data entry errors or legitimate transfers.
- **All data read as strings**: CSVs are loaded with `dtype=str` to prevent pandas from silently coercing types (e.g., treating `SKU005` as a valid string while parsing `70.0` as float). Conversion happens explicitly in the normalizer.

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
