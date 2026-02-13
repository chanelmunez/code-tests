
import os
import pytest
import pandas as pd
from reconciliation.loader import load_snapshot
from reconciliation.normalizer import normalize_dataframe
from reconciliation.validator import validate_snapshot
from reconciliation.reconciler import reconcile

DATA_DIR = "data"

def get_path(filename):
    return os.path.join(DATA_DIR, filename)

def test_load_0byte_file():
    """Test loading a truly empty (0 bytes) CSV file."""
    path = get_path("testing-0bytes.csv")
    with pytest.raises(pd.errors.EmptyDataError):
        load_snapshot(path)

def test_load_empty_table():
    """Test loading a CSV with only headers (no data)."""
    path = get_path("testing-empty.csv")
    df = load_snapshot(path)
    assert df.empty
    assert list(df.columns) == ["sku", "name", "quantity", "location", "date"]

def test_load_garbage_file():
    """Test loading a file with binary/garbage data."""
    path = get_path("testing-garbage.csv")
    # Pandas might raise ParserError or UnicodeDecodeError depending on content
    with pytest.raises((pd.errors.ParserError, UnicodeDecodeError)):
        load_snapshot(path)

def test_missing_columns():
    """Test loading a file with missing columns."""
    path = get_path("testing-missing-cols.csv")
    with pytest.raises(ValueError, match="Missing required columns"):
        load_snapshot(path)

def test_huge_file_performance():
    """Test loading and processing a larger file."""
    path = get_path("testing-huge.csv")
    df = load_snapshot(path)
    assert len(df) == 1000
    
    normalized_df, issues = normalize_dataframe(df, "snapshot_huge")
    # We generated valid data, so issues should be minimal (maybe just date normalization if any)
    # The generator used '2024-01-01', which is standard.
    # But names were "Item 1", etc.
    assert len(normalized_df) == 1000

def test_duplicate_handling_all_duplicates():
    """Test reconciliation when one file is entirely duplicates."""
    path = get_path("testing-duplicates.csv")
    df = load_snapshot(path)
    norm_df, issues = normalize_dataframe(df, "snapshot_dupes")
    val_issues = validate_snapshot(norm_df, "snapshot_dupes")
    
    # We expect duplicate errors
    duplicate_errors = [i for i in val_issues if i.issue_type == "duplicate_sku"]
    assert len(duplicate_errors) > 0
    
    # If we reconcile this against itself, everything should be skipped
    result = reconcile(norm_df, norm_df, quality_issues=val_issues)
    
    # Check that skipped_skus contains our duplicates
    assert "SKU-001" in result.skipped_skus
    assert "SKU-002" in result.skipped_skus
    
    # Since all are duplicates, nothing should be added/removed/changed/unchanged
    # Wait, in testing-duplicates.csv:
    # SKU-001 (2 rows) -> Duplicate
    # SKU-002 (2 rows) -> Duplicate
    # So ALL rows are duplicates.
    assert len(result.added) == 0
    assert len(result.removed) == 0
    assert len(result.changed) == 0
    assert len(result.unchanged) == 0
    assert len(result.skipped_skus) == 2

def test_normalization_collisions():
    """Test that distinct raw SKUs that normalize to the same value are treated as duplicates."""
    path = get_path("testing-collisions.csv")
    df = load_snapshot(path)
    norm_df, issues = normalize_dataframe(df, "snapshot_collisions")
    
    # SKU-001 and SKU001 -> Both become SKU-001
    # This should trigger a duplicate SKU error in validation
    val_issues = validate_snapshot(norm_df, "snapshot_collisions")
    
    dupe_issues = [i for i in val_issues if i.issue_type == "duplicate_sku"]
    assert len(dupe_issues) == 1
    assert dupe_issues[0].sku == "SKU-001"

def test_extreme_values():
    """Test handling of extreme integer values and long strings."""
    path = get_path("testing-extreme.csv")
    df = load_snapshot(path)
    norm_df, issues = normalize_dataframe(df, "snapshot_extreme")
    
    # Check max int
    row_max = norm_df[norm_df["sku"] == "SKU-MAX"].iloc[0]
    assert row_max["quantity"] == 999999999999
    
    # Check min int (should be flagged as negative quantity in validation)
    row_min = norm_df[norm_df["sku"] == "SKU-MIN"].iloc[0]
    assert row_min["quantity"] == -999999999999
    
    val_issues = validate_snapshot(norm_df, "snapshot_extreme")
    neg_issues = [i for i in val_issues if i.issue_type == "negative_quantity"]
    assert any(i.sku == "SKU-MIN" for i in neg_issues)

    # Check long string
    row_long = norm_df[norm_df["sku"] == "SKU-LONG"].iloc[0]
    assert len(row_long["name"]) == 1000
    assert len(row_long["location"]) == 1000

def test_reconcile_empty_dataframes():
    """Test reconciling two empty dataframes."""
    df = pd.DataFrame(columns=["sku", "name", "quantity", "location", "date"])
    result = reconcile(df, df)
    
    assert len(result.added) == 0
    assert len(result.removed) == 0
    assert len(result.changed) == 0
    assert len(result.unchanged) == 0
    assert len(result.skipped_skus) == 0
