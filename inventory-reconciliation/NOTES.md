# Notes — Inventory Reconciliation

## Approach

I built a modular pipeline that processes the snapshots in five stages: **load → normalize → validate → reconcile → report**. Each stage is a separate module with its own unit tests (204 total), making the logic easy to verify and extend.

The loader standardizes the different column names between files (`name`/`product_name`, `quantity`/`qty`, etc.) into a common schema. The normalizer cleans the raw data — fixing SKU formats, stripping whitespace, converting float quantities to integers, and normalizing date formats — while logging every correction as a quality issue. Normalization rules are configurable via YAML. The validator runs semantic checks (duplicates, negative quantities, missing values across all fields). The reconciler joins the two clean datasets by key (SKU or SKU+location composite) and classifies each item as added, removed, changed, within tolerance, or unchanged. Changed items receive a priority rating and fuzzy name similarity score. Finally, the reporter generates JSON and CSV output with optional sorting and filtering.

## Key Decisions

- **Error severity enforcement + run IDs**: Any SKU associated with an error-level quality issue (duplicate, negative quantity, fractional quantity, unparseable date, missing field) is excluded from reconciliation entirely, and the CLI exits with a non-zero status unless `--allow-errors` is explicitly provided. Every run is tagged with a `run_id` (UUID) that propagates through structured logs and the JSON report, making correlation/auditing trivial. Warnings (whitespace, float-stored integers, non-standard dates) are auto-corrected and the item proceeds normally.
- **Duplicate SKU handling**: SKU-045 appears twice in snapshot_2 with conflicting data (different names, quantities, and locations). Rather than guess which row is correct, I excluded it from reconciliation entirely and flagged it prominently in the quality issues report.
- **Fractional quantities rejected**: A value like `70.5` is treated as an error (inventory counts should be whole numbers), while `70.0` is safely converted to `70` with a warning. This prevents silent precision loss from `int(float(...))` truncation.
- **SKU normalization**: SKUs like `SKU005`, `sku-008`, and `SKU018` are normalized to `SKU-NNN` format (uppercase, hyphenated, zero-padded). Without this, these items would incorrectly appear as "removed" from one snapshot and "added" to the other.
- **Composite key support**: The default mode uses SKU as the sole key. With `--key-mode sku_location`, the system uses (SKU, location) as a composite key — allowing the same SKU to exist in multiple warehouses without being flagged as a duplicate.
- **Variance tolerance**: Configurable tolerance bands (`--tolerance 5` or `--tolerance-pct 2`) allow ignoring small quantity fluctuations that may be counting errors rather than real shrinkage.
- **Fuzzy name matching**: When a SKU matches between snapshots but the product name differs, a Levenshtein similarity score (0.0–1.0) is computed. This helps distinguish typos from legitimate product renames.
- **Priority assignment**: Changed items receive a priority based on the magnitude of change — high (>10% variance or name change), medium (5–10%), low (<5%). This helps reviewers focus on what matters.
- **Configurable normalization**: All normalization rules (SKU pattern, date formats, quantity handling, location casing) are configurable via YAML, with sensible defaults matching the current behavior.
- **All data read as strings**: CSVs are loaded with `dtype=str` to prevent pandas from silently coercing types.
- **Packaging & automation**: The repo now includes a `pyproject.toml`, `Dockerfile`, and GitHub Actions workflow (`.github/workflows/tests.yml`) so the tool can be installed, containerized, and tested consistently.

## Health Statistics

The system computes an inventory health score:
- **Accuracy rate**: Percentage of common items that are unchanged (or within tolerance)
- **Total variance**: Sum of all absolute quantity deltas across changed items
- **Variance by location**: Breakdown of variance by warehouse
- **Data quality score**: Percentage of rows that required no normalization corrections

## Data Quality Issues Found

| Severity | Issue | Count | Examples |
|----------|-------|-------|----------|
| Warning | Whitespace in product names | 5 | ` Widget B`, `Cable Ties 100pk `, ` HDMI Cable 3ft ` |
| Warning | SKU format inconsistency | 3 | `SKU005`, `sku-008`, `SKU018` |
| Warning | Float quantities | 2 | `70.0`, `80.00` |
| Warning | Non-standard date format | 1 | `01/15/2024` instead of `2024-01-15` |
| Error | Duplicate SKU | 1 | SKU-045 appears twice with conflicting data |
| Error | Negative quantity | 1 | SKU-045 has qty `-5` |

## CLI Usage

```
python reconcile.py                                    # Basic run
python reconcile.py --key-mode sku_location            # Composite key
python reconcile.py --tolerance 5                      # Ignore deltas <= 5
python reconcile.py --tolerance-pct 2                  # Ignore deltas <= 2%
python reconcile.py --config custom.yaml               # Custom normalization rules
python reconcile.py --sort delta --filter changed      # Sort by largest delta, show only changes
python reconcile.py --log-format json                  # Structured JSON logging
```
