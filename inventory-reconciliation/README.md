# Inventory Reconciliation

This repository contains a fully working pipeline that reconciles two warehouse inventory snapshots and surfaces the operational deltas plus any data-quality issues encountered along the way.

## Overview

The workflow is implemented in `reconcile.py` and the `reconciliation/` package:

1. **Load** both CSV snapshots via `reconciliation.loader` (column aliases, deterministic schema ordering, empty strings preserved).
2. **Normalize** fields with `reconciliation.normalizer` (SKU canonicalization, Unicode/name/location cleanup, numeric/date parsing) while logging `QualityIssue`s.
3. **Validate** the cleaned data through `reconciliation.validator` (duplicates, missing required fields, negative quantities, etc.).
4. **Reconcile** using `reconciliation.reconciler`, classifying SKUs as added/removed/changed/unchanged and skipping SKUs tied to error-level quality issues.
5. **Report** with `reconciliation.reporter`, emitting a structured JSON report plus a flat CSV summary.

Extensive unit, integration, CLI, and hardening tests live under `tests/` (172 tests as of 2026-02-13).

## Getting Started

### Prerequisites

- Python 3.12+
- `pip` for installing dependencies

Install the dependencies:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### Running the Reconciliation

```bash
python reconcile.py \
  --snapshot1 data/snapshot_1.csv \
  --snapshot2 data/snapshot_2.csv \
  --output-dir output
```

Key CLI flags:

- `--snapshot1/--snapshot2`: paths to the CSV snapshots (default to `data/snapshot_1.csv` and `data/snapshot_2.csv`).
- `--output-dir`: destination directory for reports (defaults to `output/`).
- `--log-format`: `text` or `json` log output.

The script streams progress to stdout/stderr and writes two artefacts in the output directory:

1. `reconciliation_report.json` – structured metadata, summary counts, categorized SKUs, pipeline log, and data-quality issues.
2. `reconciliation_summary.csv` – flat table of every reconciled SKU with quantity/name/location deltas.

### Running Tests

```bash
pytest
```

The suite covers loaders, normalizers, validators, reconcilers, reporters, CLI invocations, hardening scenarios, and regression cases distilled from the ongoing ADVICE log.

## Project Notes

- Architectural decisions, assumptions, and data-quality findings are documented in `NOTES.md`.
- High-level progress, remaining risks, and review checkpoints are tracked in `PROGRESS.md` and `ADVICE.md`.

## Data

The assessment ships with sample data under `data/`:

- `snapshot_1.csv` – baseline inventory from one week ago.
- `snapshot_2.csv` – inventory collected one week later (contains intentional quality defects such as duplicate SKUs, typoed identifiers, float quantities, etc.).

You can supply alternative files via the CLI flags described above.
