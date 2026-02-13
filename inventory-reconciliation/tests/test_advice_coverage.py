
import pytest
import pandas as pd
from reconciliation.loader import load_snapshot
from reconciliation.normalizer import normalize_sku, normalize_quantity, normalize_date
from reconciliation.reconciler import reconcile
from reconciliation.models import QualityIssue

# 1. Loader Robustness: Empty Strings
def test_loader_reads_empty_strings_not_nan(tmp_path):
    """Verify that pd.read_csv with keep_default_na=False reads empty cells as ''."""
    csv_path = tmp_path / "test_empty_cells.csv"
    csv_path.write_text("sku,name,quantity,location,date\nSKU-001,,10,,\n")
    
    df = load_snapshot(csv_path)
    row = df.iloc[0]
    
    # Assertions for empty strings
    assert row["name"] == "", f"Expected empty string, got {repr(row['name'])}"
    assert row["location"] == "", f"Expected empty string, got {repr(row['location'])}"
    assert row["date"] == "", f"Expected empty string, got {repr(row['date'])}"
    
    # Ensure it's not "nan" string or float NaN
    assert row["name"] is not None
    assert row["name"] != "nan"

# 2. Normalizer Robustness: None/NaN Guards
def test_normalize_sku_guards():
    assert normalize_sku(None) == ""
    assert normalize_sku(float("nan")) == ""

def test_normalize_quantity_guards():
    assert normalize_quantity(None) is None
    assert normalize_quantity("") is None

def test_normalize_date_guards():
    assert normalize_date(None) is None
    assert normalize_date("") is None
    assert normalize_date(float("nan")) is None

# 3. Severity Enforcement: unique error SKU skipped
def test_reconciler_skips_unique_error_sku():
    """Verify that a unique SKU with an error-level issue is excluded."""
    # Create valid dataframes
    df1 = pd.DataFrame({
        "sku": ["SKU-GOOD"],
        "name": ["Good Item"],
        "quantity": [10],
        "location": ["A"],
        "date": ["2024-01-01"]
    })
    
    df2 = pd.DataFrame({
        "sku": ["SKU-BAD"],
        "name": ["Bad Item"],
        "quantity": [-5], # Negative quantity -> Error
        "location": ["A"],
        "date": ["2024-01-01"]
    })
    
    # Create the QualityIssue manually (simulating validator)
    issues = [
        QualityIssue(
            sku="SKU-BAD",
            field="quantity",
            issue_type="negative_quantity",
            detail="Negative quantity",
            snapshot="snapshot_2",
            severity="error"
        )
    ]
    
    result = reconcile(df1, df2, quality_issues=issues)
    
    # SKU-GOOD is in snapshot 1 (removed)
    assert any(i.sku == "SKU-GOOD" for i in result.removed)
    
    # SKU-BAD is in snapshot 2 (added) BUT has error, so should be SKIPPED
    # It should NOT be in 'added'
    assert not any(i.sku == "SKU-BAD" for i in result.added)
    
    # It should be in skipped_skus
    assert "SKU-BAD" in result.skipped_skus

# 4. Invalid Date Handling
def test_invalid_date_normalization():
    """Verify that invalid dates return None (which validator will catch)."""
    assert normalize_date("13/40/2024") is None
    assert normalize_date("not-a-date") is None
