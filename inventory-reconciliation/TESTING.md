# QA Assessment - Initial Review

**Status**: Implementation marked complete in PROGRESS.md.
**Code Inspection**: Pending authorization.

## Initial Critiques based on PROGRESS.md

### 1. Duplicate Handling Strategy
- **Observation**: "Flag duplicate SKUs and exclude them from reconciliation entirely."
- **Critique**: This is a safe approach but might obscure data loss.
- **QA Question**: If `SKU-A` appears twice in Snapshot 2 (one valid, one invalid), are *both* excluded? This effectively removes `SKU-A` from the inventory count entirely, which is a high-risk behavior for an inventory system.
- **Recommendation**: Verify test coverage ensures users are explicitly warned about *which* SKUs were dropped so they don't assume zero inventory means "out of stock".

### 2. Normalization & strictness
- **Observation**: Issues like "SKU005 (missing hyphen)" and "sku-008 (lowercase)" are identified.
- **Critique**: How aggressive is the normalization?
- **QA Question**: Does `SKU005` become `SKU-005`? If so, is there a risk of collision if `SKU-005` (correct format) already exists?
- **Edge Case**: `SKU-005` and `SKU005` both present in the same file. Normalizing one might create a duplicate where none existed effectively.

### 3. "Changed" Definition
- **Observation**: "Track all changes — quantity, product name, and location/warehouse".
- **Critique**: Tracking location changes is tricky if the SKU is the only primary key.
- **QA Question**: If `SKU-X` moves from Warehouse A to Warehouse B, is that a "Change" or just a state update? If `SKU-X` exists in *both* Warehouse A and B in the same snapshot, that's a duplicate SKU violation per the current rules.
- **Edge Case**: Split inventory. If the system doesn't support (SKU + Location) as a composite key, it cannot handle the same item being in multiple locations. The "Duplicate SKU" issue (Issue 6) suggests this is treated as an error, which limits the system's real-world applicability.

### 4. Test Coverage Gaps (Hypothetical)
- **Observation**: 105 tests passing.
- **Critique**: High number, but "positive" tests often outweigh "negative" ones.
- **Recommended Tests**:
    - **Empty Files**: `snapshot_2` is completely empty (did we sell everything or is the file broken?).
    - **Huge Files**: 1 million rows (Memory usage check).
    - **Binary Garbage**: A CSV containing a binary blob or null bytes in the middle.
    - **Permission Errors**: Read-only output directory.

## Next Steps
Awaiting instruction to begin code inspection for static analysis and boundary testing.
