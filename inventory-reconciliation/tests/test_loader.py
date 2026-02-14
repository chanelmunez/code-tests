"""Tests for the CSV loading module."""

import csv
from pathlib import Path

import pytest

from reconciliation.loader import load_snapshot

DATA_DIR = Path(__file__).parent.parent / "data"


@pytest.fixture
def simple_csv(tmp_path) -> Path:
    """Create a simple CSV with standard column names."""
    path = tmp_path / "standard.csv"
    path.write_text("sku,name,quantity,location,last_counted\nSKU-001,Widget,100,WA,2024-01-08\n")
    return path


@pytest.fixture
def aliased_csv(tmp_path) -> Path:
    """Create a CSV with alternate column names (like snapshot_2)."""
    path = tmp_path / "aliased.csv"
    path.write_text("sku,product_name,qty,warehouse,updated_at\nSKU-001,Widget,100,WA,2024-01-15\n")
    return path


class TestLoadSnapshot:
    """Tests for CSV loading and column normalization."""

    def test_loads_standard_columns(self, simple_csv):
        df = load_snapshot(simple_csv)
        assert set(df.columns) == {"sku", "name", "quantity", "location", "date"}

    def test_maps_aliased_columns(self, aliased_csv):
        df = load_snapshot(aliased_csv)
        assert set(df.columns) == {"sku", "name", "quantity", "location", "date"}
        assert df.iloc[0]["name"] == "Widget"

    def test_reads_as_strings(self, simple_csv):
        df = load_snapshot(simple_csv)
        # Everything should be loaded as string dtype initially
        assert df["quantity"].iloc[0] == "100"

    def test_file_not_found(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            load_snapshot(tmp_path / "nonexistent.csv")

    def test_missing_columns(self, tmp_path):
        path = tmp_path / "bad.csv"
        path.write_text("sku,price\nSKU-001,9.99\n")
        with pytest.raises(ValueError, match="Missing required columns"):
            load_snapshot(path)

    def test_loads_real_snapshot_1(self):
        df = load_snapshot(DATA_DIR / "snapshot_1.csv")
        assert len(df) == 75
        assert set(df.columns) == {"sku", "name", "quantity", "location", "date"}

    def test_loads_real_snapshot_2(self):
        df = load_snapshot(DATA_DIR / "snapshot_2.csv")
        # 79 rows: SKU-001 to SKU-080 minus SKU-025/SKU-026, plus duplicate SKU-045
        assert len(df) == 79
        assert set(df.columns) == {"sku", "name", "quantity", "location", "date"}

    def test_handles_whitespace_in_column_names(self, tmp_path):
        path = tmp_path / "whitespace.csv"
        path.write_text(" sku , name , quantity , location , last_counted \nSKU-001,W,1,WA,2024-01-08\n")
        df = load_snapshot(path)
        assert set(df.columns) == {"sku", "name", "quantity", "location", "date"}

    def test_handles_utf8_bom(self, tmp_path):
        """CSV exported from Windows Excel with UTF-8 BOM should load correctly."""
        path = tmp_path / "bom.csv"
        path.write_bytes(b"\xef\xbb\xbfsku,name,quantity,location,last_counted\nSKU-001,Widget,10,WA,2024-01-08\n")
        df = load_snapshot(path)
        assert "sku" in df.columns
        assert df.iloc[0]["sku"] == "SKU-001"
