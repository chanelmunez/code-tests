"""Tests for the data normalization module."""

import math

import pandas as pd
import pytest

from reconciliation.normalizer import (
    normalize_dataframe,
    normalize_date,
    normalize_quantity,
    normalize_sku,
)


class TestNormalizeSku:
    """Tests for SKU normalization."""

    def test_already_normalized(self):
        assert normalize_sku("SKU-001") == "SKU-001"

    def test_missing_hyphen(self):
        assert normalize_sku("SKU005") == "SKU-005"

    def test_lowercase(self):
        assert normalize_sku("sku-008") == "SKU-008"

    def test_lowercase_no_hyphen(self):
        assert normalize_sku("sku003") == "SKU-003"

    def test_leading_trailing_whitespace(self):
        assert normalize_sku(" SKU-010 ") == "SKU-010"

    def test_three_digit_number(self):
        assert normalize_sku("SKU-100") == "SKU-100"

    def test_single_digit_padded(self):
        assert normalize_sku("SKU-1") == "SKU-001"

    def test_two_digit_padded(self):
        assert normalize_sku("SKU-18") == "SKU-018"

    def test_none_returns_empty(self):
        assert normalize_sku(None) == ""

    def test_nan_returns_empty(self):
        assert normalize_sku(float("nan")) == ""

    def test_empty_string_returns_empty(self):
        assert normalize_sku("") == ""

    def test_whitespace_only_returns_empty(self):
        assert normalize_sku("   ") == ""


class TestNormalizeQuantity:
    """Tests for quantity normalization."""

    def test_integer_string(self):
        assert normalize_quantity("100") == 100

    def test_float_string_integer_value(self):
        assert normalize_quantity("70.0") == 70

    def test_float_with_trailing_zeros(self):
        assert normalize_quantity("80.00") == 80

    def test_negative_integer(self):
        assert normalize_quantity("-5") == -5

    def test_whitespace(self):
        assert normalize_quantity(" 42 ") == 42

    def test_invalid_returns_none(self):
        assert normalize_quantity("abc") is None

    def test_empty_returns_none(self):
        assert normalize_quantity("") is None

    def test_none_returns_none(self):
        assert normalize_quantity(None) is None

    def test_zero(self):
        assert normalize_quantity("0") == 0

    def test_fractional_value_returns_none(self):
        """Genuine fractions like 70.5 should be rejected, not silently truncated."""
        assert normalize_quantity("70.5") is None

    def test_fractional_negative_returns_none(self):
        assert normalize_quantity("-3.7") is None

    def test_small_fraction_returns_none(self):
        assert normalize_quantity("0.1") is None


class TestNormalizeDate:
    """Tests for date normalization."""

    def test_iso_format(self):
        assert normalize_date("2024-01-15") == "2024-01-15"

    def test_us_format(self):
        assert normalize_date("01/15/2024") == "2024-01-15"

    def test_whitespace(self):
        assert normalize_date(" 2024-01-15 ") == "2024-01-15"

    def test_invalid_returns_none(self):
        assert normalize_date("not-a-date") is None

    def test_empty_returns_none(self):
        assert normalize_date("") is None

    def test_none_returns_none(self):
        assert normalize_date(None) is None

    def test_nan_returns_none(self):
        assert normalize_date(float("nan")) is None

    def test_impossible_date_returns_none(self):
        assert normalize_date("13/40/2024") is None


class TestNormalizeDataframe:
    """Tests for full DataFrame normalization."""

    def test_normalizes_skus(self, raw_snapshot_strings):
        df, issues = normalize_dataframe(raw_snapshot_strings, "test")
        assert list(df["sku"]) == ["SKU-001", "SKU-005", "SKU-003", "SKU-004"]

    def test_strips_name_whitespace(self, raw_snapshot_strings):
        df, issues = normalize_dataframe(raw_snapshot_strings, "test")
        assert list(df["name"]) == ["Widget A", "Widget B", "Gadget Pro", "Gadget Lite"]

    def test_converts_quantities_to_int(self, raw_snapshot_strings):
        df, issues = normalize_dataframe(raw_snapshot_strings, "test")
        assert list(df["quantity"]) == [100, 70, 200, 30]

    def test_normalizes_dates(self, raw_snapshot_strings):
        df, issues = normalize_dataframe(raw_snapshot_strings, "test")
        assert list(df["date"]) == ["2024-01-08", "2024-01-08", "2024-01-08", "2024-01-08"]

    def test_reports_sku_issues(self, raw_snapshot_strings):
        _, issues = normalize_dataframe(raw_snapshot_strings, "test")
        sku_issues = [i for i in issues if i.issue_type == "sku_format"]
        # SKU005 (missing hyphen), sku-003 (lowercase), " SKU-004 " (whitespace)
        assert len(sku_issues) == 3

    def test_reports_whitespace_issues(self, raw_snapshot_strings):
        _, issues = normalize_dataframe(raw_snapshot_strings, "test")
        ws_issues = [i for i in issues if i.issue_type == "whitespace"]
        # " Widget B", "Gadget Pro ", " Gadget Lite "
        assert len(ws_issues) == 3

    def test_reports_float_quantity_issues(self, raw_snapshot_strings):
        _, issues = normalize_dataframe(raw_snapshot_strings, "test")
        float_issues = [i for i in issues if i.issue_type == "float_quantity"]
        assert len(float_issues) == 1
        assert float_issues[0].sku == "SKU-005"

    def test_reports_date_format_issues(self, raw_snapshot_strings):
        _, issues = normalize_dataframe(raw_snapshot_strings, "test")
        date_issues = [i for i in issues if i.issue_type == "date_format"]
        assert len(date_issues) == 1
        assert date_issues[0].original_value == "01/08/2024"

    def test_does_not_modify_original(self, raw_snapshot_strings):
        original_skus = list(raw_snapshot_strings["sku"])
        normalize_dataframe(raw_snapshot_strings, "test")
        assert list(raw_snapshot_strings["sku"]) == original_skus

    def test_snapshot_label_in_issues(self, raw_snapshot_strings):
        _, issues = normalize_dataframe(raw_snapshot_strings, "my_snapshot")
        assert all(i.snapshot == "my_snapshot" for i in issues)

    def test_fractional_quantity_flagged_as_error(self):
        """A genuine fraction (70.5) should produce an error-level issue."""
        df = pd.DataFrame({
            "sku": ["SKU-001"],
            "name": ["Widget"],
            "quantity": ["70.5"],
            "location": ["WA"],
            "date": ["2024-01-08"],
        })
        normalized, issues = normalize_dataframe(df, "test")
        frac_issues = [i for i in issues if i.issue_type == "fractional_quantity"]
        assert len(frac_issues) == 1
        assert frac_issues[0].severity == "error"
        assert frac_issues[0].sku == "SKU-001"
        # Quantity should be None (rejected)
        assert normalized.iloc[0]["quantity"] is None

    def test_unparseable_quantity_flagged_as_error(self):
        """A completely unparseable quantity should produce an error."""
        df = pd.DataFrame({
            "sku": ["SKU-001"],
            "name": ["Widget"],
            "quantity": ["abc"],
            "location": ["WA"],
            "date": ["2024-01-08"],
        })
        _, issues = normalize_dataframe(df, "test")
        invalid_issues = [i for i in issues if i.issue_type == "invalid_quantity"]
        assert len(invalid_issues) == 1
        assert invalid_issues[0].severity == "error"

    def test_unparseable_date_flagged_as_error(self):
        """An unparseable date should produce an error-level issue."""
        df = pd.DataFrame({
            "sku": ["SKU-001"],
            "name": ["Widget"],
            "quantity": ["100"],
            "location": ["WA"],
            "date": ["13/40/2024"],
        })
        _, issues = normalize_dataframe(df, "test")
        date_issues = [i for i in issues if i.issue_type == "invalid_date"]
        assert len(date_issues) == 1
        assert date_issues[0].severity == "error"
        assert date_issues[0].original_value == "13/40/2024"

    def test_valid_nonstandard_date_is_warning_not_error(self):
        """01/15/2024 is parseable (just non-standard) — should be a warning, not error."""
        df = pd.DataFrame({
            "sku": ["SKU-001"],
            "name": ["Widget"],
            "quantity": ["100"],
            "location": ["WA"],
            "date": ["01/15/2024"],
        })
        _, issues = normalize_dataframe(df, "test")
        date_issues = [i for i in issues if i.field == "date"]
        assert len(date_issues) == 1
        assert date_issues[0].issue_type == "date_format"
        assert date_issues[0].severity == "warning"
