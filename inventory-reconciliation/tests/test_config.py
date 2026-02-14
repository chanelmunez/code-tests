"""Tests for the configuration loader and configurable normalization."""

import pandas as pd
import pytest

from reconciliation.config import DEFAULT_CONFIG, load_config
from reconciliation.normalizer import (
    normalize_dataframe,
    normalize_date,
    normalize_quantity,
    normalize_sku,
)


class TestLoadConfig:
    """Tests for YAML config loading."""

    def test_defaults_when_no_file(self):
        config = load_config(None)
        assert config["sku"]["pattern"] == DEFAULT_CONFIG["sku"]["pattern"]
        assert config["quantity"]["allow_fractional"] is False
        assert config["date"]["output_format"] == "%Y-%m-%d"

    def test_loads_yaml_file(self, tmp_path):
        cfg_file = tmp_path / "custom.yaml"
        cfg_file.write_text("quantity:\n  allow_fractional: true\n")
        config = load_config(cfg_file)
        assert config["quantity"]["allow_fractional"] is True
        # Other defaults preserved
        assert config["sku"]["case"] == "upper"

    def test_deep_merge_preserves_unset_keys(self, tmp_path):
        cfg_file = tmp_path / "partial.yaml"
        cfg_file.write_text("date:\n  output_format: '%d/%m/%Y'\n")
        config = load_config(cfg_file)
        assert config["date"]["output_format"] == "%d/%m/%Y"
        assert config["date"]["formats"] == ["%Y-%m-%d", "%m/%d/%Y", "%d-%b-%Y", "%Y/%m/%d"]

    def test_file_not_found(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            load_config(tmp_path / "nonexistent.yaml")

    def test_empty_yaml_returns_defaults(self, tmp_path):
        cfg_file = tmp_path / "empty.yaml"
        cfg_file.write_text("")
        config = load_config(cfg_file)
        assert config == DEFAULT_CONFIG


class TestConfigurableNormalization:
    """Tests for config-driven normalization behavior."""

    def test_custom_sku_pattern(self):
        config = {"pattern": r"^ITEM-?(\d+)$", "format": "ITEM-{:04d}", "case": "upper"}
        assert normalize_sku("ITEM005", config) == "ITEM-0005"
        assert normalize_sku("item-42", config) == "ITEM-0042"

    def test_allow_fractional_quantities(self):
        config = {"allow_fractional": True, "allow_negative": False}
        assert normalize_quantity("70.5", config) == 70

    def test_reject_fractional_by_default(self):
        assert normalize_quantity("70.5") is None

    def test_custom_date_format(self):
        config = {
            "formats": ["%d-%m-%Y", "%Y-%m-%d"],
            "output_format": "%d/%m/%Y",
        }
        assert normalize_date("15-01-2024", config) == "15/01/2024"
        assert normalize_date("2024-01-15", config) == "15/01/2024"

    def test_dataframe_with_custom_config(self):
        config = {
            "sku": DEFAULT_CONFIG["sku"],
            "name": DEFAULT_CONFIG["name"],
            "quantity": {"allow_fractional": True, "allow_negative": False},
            "location": DEFAULT_CONFIG["location"],
            "date": DEFAULT_CONFIG["date"],
        }
        df = pd.DataFrame({
            "sku": ["SKU-001"],
            "name": ["Widget"],
            "quantity": ["70.5"],
            "location": ["WA"],
            "date": ["2024-01-08"],
        })
        normalized, issues = normalize_dataframe(df, "test", config=config)
        # With allow_fractional, 70.5 → 70 (truncated, not rejected)
        assert normalized.iloc[0]["quantity"] == 70

    def test_no_title_case_location(self):
        config = {
            "sku": DEFAULT_CONFIG["sku"],
            "name": DEFAULT_CONFIG["name"],
            "quantity": DEFAULT_CONFIG["quantity"],
            "location": {"title_case": False, "unicode_normalize": "NFKC"},
            "date": DEFAULT_CONFIG["date"],
        }
        df = pd.DataFrame({
            "sku": ["SKU-001"],
            "name": ["Widget"],
            "quantity": ["100"],
            "location": ["warehouse a"],
            "date": ["2024-01-08"],
        })
        normalized, _ = normalize_dataframe(df, "test", config=config)
        assert normalized.iloc[0]["location"] == "warehouse a"
