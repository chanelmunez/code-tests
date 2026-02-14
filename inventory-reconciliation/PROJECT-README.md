# Inventory Reconciliation (Solution Guide)

This document elaborates on how to run and extend the implementation in this repo. The original problem statement remains in `README.md` per the assessment instructions.

## Overview

The workflow is implemented in `reconcile.py` and the `reconciliation/` package:

1. **Load** CSV snapshots via `reconciliation.loader` (column aliases, deterministic schema order, empty strings preserved).
2. **Normalize** fields with `reconciliation.normalizer` (SKU canonicalization, Unicode/name/location cleanup, numeric/date parsing) while logging `QualityIssue`s.
3. **Validate** with `reconciliation.validator` (duplicates, missing required fields, negative quantities, etc.).
4. **Reconcile** using `reconciliation.reconciler`, classifying SKUs as added/removed/changed/unchanged/within_tolerance. Error-level SKUs are skipped.
5. **Report** via `reconciliation.reporter`, emitting a structured JSON report plus a flat CSV summary.

## Getting Started

### Prerequisites

- Python 3.12+
- `pip`

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
  --output-dir output \
  --allow-errors
```

> **Note:** By default the CLI aborts when error-level quality issues are detected. The bundled sample data contains such issues (duplicates, negatives), so include `--allow-errors` if you want to generate reports from the provided fixtures.

Key CLI flags:

- `--snapshot1/--snapshot2`: CSV paths (defaults provided).
- `--output-dir`: Destination directory for JSON/CSV output.
- `--allow-errors`: Opt-in to continue even when errors exist (default: fail fast).
- `--log-format`: `text` or `json` log output.
- `--key-mode`, `--tolerance`, `--tolerance-pct`, `--sort`, `--filter`: Advanced reconciliation/reporting controls.

### Running Tests

```bash
pytest
```

## Project Notes

Specialized docs live in:

- `NOTES.md` – architecture/theory, known limitations, roadmap.
- `PROGRESS.md` – milestone history and outstanding work.
- `TESTING.md` / `CODE-TESTING-PROGRESS.md` – QA scope, test matrices.
- `ADVICE.md` – running critique log.

## Data

Sample data lives in `data/`. You can supply alternative snapshots via the `--snapshot` flags.

## Operational Tips

- Outputs (`output/`) and coverage artefacts are ignored via `.gitignore`; tests use their own temp directories.
- Every run is tagged with a unique `run_id` that appears in logs, the JSON report metadata, and the pipeline log for easy auditing.
- A GitHub Actions workflow (`.github/workflows/tests.yml`) runs `pytest` in CI.

## Packaging & Deployment

- `pyproject.toml` defines dependencies and enables `pip install .` workflows.
- `Dockerfile` bundles the project into a reproducible container image (see CMD for defaults).
- `requirements.txt` remains for lightweight installs/CI bootstrap.

## Future Enhancements

The `ADVICE.md` backlog captures feature ideas such as ABC-based cycle counting, master-data enrichment, and Polars-based performance work. Contributions welcome!
