"""Shared pytest fixtures for inventory reconciliation tests."""

import pandas as pd
import pytest


@pytest.fixture
def clean_snapshot_1() -> pd.DataFrame:
    """A small, clean snapshot with no quality issues."""
    return pd.DataFrame({
        "sku": ["SKU-001", "SKU-002", "SKU-003", "SKU-004", "SKU-005"],
        "name": ["Widget A", "Widget B", "Gadget Pro", "Gadget Lite", "Cable 6ft"],
        "quantity": [100, 50, 200, 30, 500],
        "location": ["Warehouse A", "Warehouse A", "Warehouse B", "Warehouse A", "Warehouse C"],
        "date": ["2024-01-08", "2024-01-08", "2024-01-08", "2024-01-08", "2024-01-08"],
    })


@pytest.fixture
def clean_snapshot_2() -> pd.DataFrame:
    """A matching snapshot with some quantity changes, one removal, one addition."""
    return pd.DataFrame({
        "sku": ["SKU-001", "SKU-002", "SKU-003", "SKU-005", "SKU-006"],
        "name": ["Widget A", "Widget B", "Gadget Pro", "Cable 6ft", "Cable 10ft"],
        "quantity": [90, 50, 210, 480, 100],
        "location": ["Warehouse A", "Warehouse A", "Warehouse B", "Warehouse C", "Warehouse C"],
        "date": ["2024-01-15", "2024-01-15", "2024-01-15", "2024-01-15", "2024-01-15"],
    })


@pytest.fixture
def raw_snapshot_strings() -> pd.DataFrame:
    """A snapshot loaded as all-string types (simulating pd.read_csv with dtype=str)."""
    return pd.DataFrame({
        "sku": ["SKU-001", "SKU005", "sku-003", " SKU-004 "],
        "name": ["Widget A", " Widget B", "Gadget Pro ", " Gadget Lite "],
        "quantity": ["100", "70.0", "200", "30"],
        "location": ["Warehouse A", "Warehouse A", "Warehouse B", "Warehouse A"],
        "date": ["2024-01-08", "01/08/2024", "2024-01-08", "2024-01-08"],
    })


@pytest.fixture
def snapshot_with_duplicates() -> pd.DataFrame:
    """Snapshot containing a duplicate SKU."""
    return pd.DataFrame({
        "sku": ["SKU-001", "SKU-002", "SKU-002", "SKU-003"],
        "name": ["Widget A", "Widget B", "Widget B v2", "Gadget Pro"],
        "quantity": [100, 50, -5, 200],
        "location": ["Warehouse A", "Warehouse A", "Warehouse B", "Warehouse B"],
        "date": ["2024-01-15", "2024-01-15", "2024-01-15", "2024-01-15"],
    })


@pytest.fixture
def snapshot_with_negatives() -> pd.DataFrame:
    """Snapshot containing negative quantities."""
    return pd.DataFrame({
        "sku": ["SKU-001", "SKU-002", "SKU-003"],
        "name": ["Widget A", "Widget B", "Gadget Pro"],
        "quantity": [100, -10, 200],
        "location": ["Warehouse A", "Warehouse A", "Warehouse B"],
        "date": ["2024-01-15", "2024-01-15", "2024-01-15"],
    })
