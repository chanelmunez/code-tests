# Inventory Reconciliation

## Background

You're working with inventory data from a warehouse management system. Two snapshots were taken a week apart, and you need to reconcile them to understand what changed.

## Task

Write a Python script that:

1. **Compares** the two inventory snapshots (`data/snapshot_1.csv` and `data/snapshot_2.csv`)
2. **Identifies**:
   - Items present in both snapshots (and whether quantities changed)
   - Items only in snapshot 1 (removed/sold out)
   - Items only in snapshot 2 (newly added)
   - Any data quality issues worth flagging
3. **Outputs** a structured report (CSV or JSON)
4. **Includes tests** for your reconciliation logic

## Deliverables

1. `reconcile.py` (or similar) - your reconciliation script
2. `tests/` - test coverage for your logic
3. `output/` - your reconciliation results
4. `NOTES.md` - brief write-up (~half page):
   - Key decisions or assumptions you made
   - Any data quality issues you found
   - How you approached the problem

## Data

- `data/snapshot_1.csv` - inventory snapshot from one week ago
- `data/snapshot_2.csv` - current inventory snapshot

The data may contain quality issues typical of real-world systems. Your solution should handle these appropriately.

## Guidelines

- Use Python 3.10+
- You may use any libraries you find helpful
- AI assistance is allowed and expected
- Focus on correctness and clarity over performance
- Commit your work as you go (we'll look at git history)

## Time Estimate

~2 hours of focused work (most candidates complete in 1.5-3 hours)

## Submission

Push your completed work to your repository and let us know when you're done.

