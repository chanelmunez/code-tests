
import pytest
import pandas as pd
from reconciliation.normalizer import normalize_sku, normalize_quantity, normalize_date, normalize_dataframe
from reconciliation.models import QualityIssue

# 1. Unicode Normalization (NFKC)
def test_unicode_normalization():
    # 'Café' can be written as 'Cafe\u0301' (decomposed) or 'Caf\u00e9' (composed)
    # They look the same but are different bytes.
    name_composed = "Caf\u00e9"
    name_decomposed = "Cafe\u0301"
    
    assert name_composed != name_decomposed
    
    # We want them to reconcile as the same item
    df = pd.DataFrame({
        "sku": ["SKU-001", "SKU-002"],
        "name": [name_composed, name_decomposed],
        "quantity": [10, 10],
        "location": ["A", "A"],
        "date": ["2024-01-01", "2024-01-01"]
    })
    
    # This currently fails if we don't normalize unicode
    norm_df, _ = normalize_dataframe(df, "test")
    names = norm_df["name"].tolist()
    
    # Ideally, these should be identical after normalization
    # If they aren't, a "change" will be detected falsely
    assert names[0] == names[1], f"Unicode mismatch: {names[0]!r} vs {names[1]!r}"

# 2. Location Case Sensitivity
def test_location_case_normalization():
    df = pd.DataFrame({
        "sku": ["SKU-001", "SKU-002"],
        "name": ["A", "B"],
        "quantity": [1, 1],
        "location": ["Warehouse A", "warehouse a"], # Should be same
        "date": ["2024-01-01", "2024-01-01"]
    })
    
    norm_df, _ = normalize_dataframe(df, "test")
    locs = norm_df["location"].tolist()
    assert locs[0] == locs[1], f"Location case mismatch: {locs[0]!r} vs {locs[1]!r}"

# 3. Date Bounds (Future/Past)
def test_date_bounds():
    # This shouldn't crash, but maybe we want to flag it?
    # Current implementation just checks valid format.
    # Future enhancement: flag "Year 3000" as suspicious.
    raw_date = "3000-01-01"
    normalized = normalize_date(raw_date)
    # If we implement bounds checking, this might return None or trigger an issue later
    pass

# 4. Euro-style quantities
def test_euro_quantities():
    # "1.000" in US is 1.0, in EU is 1000
    # "1,000" in US is 1000, in EU is 1.0
    # Current float() logic assumes US locale usually.
    # We should probably reject ambiguous "X.XXX" if we can't be sure, 
    # OR explicitely document that we only support US locale.
    pass
