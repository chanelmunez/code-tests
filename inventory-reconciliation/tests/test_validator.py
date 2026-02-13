"""Tests for the data validation module."""

import pandas as pd
import pytest

from reconciliation.validator import (
    find_duplicate_skus,
    find_negative_quantities,
    find_null_fields,
    get_duplicate_skus,
    validate_snapshot,
)


class TestFindDuplicateSkus:
    """Tests for duplicate SKU detection."""

    def test_no_duplicates(self, clean_snapshot_1):
        issues = find_duplicate_skus(clean_snapshot_1, "test")
        assert len(issues) == 0

    def test_detects_duplicates(self, snapshot_with_duplicates):
        issues = find_duplicate_skus(snapshot_with_duplicates, "test")
        assert len(issues) == 1
        assert issues[0].sku == "SKU-002"
        assert issues[0].issue_type == "duplicate_sku"
        assert issues[0].severity == "error"

    def test_duplicate_detail_contains_both_rows(self, snapshot_with_duplicates):
        issues = find_duplicate_skus(snapshot_with_duplicates, "test")
        assert "Widget B" in issues[0].detail
        assert "Widget B v2" in issues[0].detail

    def test_multiple_duplicate_groups(self):
        df = pd.DataFrame({
            "sku": ["SKU-001", "SKU-001", "SKU-002", "SKU-002"],
            "name": ["A", "A2", "B", "B2"],
            "quantity": [10, 20, 30, 40],
            "location": ["WA", "WB", "WA", "WB"],
            "date": ["2024-01-01"] * 4,
        })
        issues = find_duplicate_skus(df, "test")
        assert len(issues) == 2


class TestFindNegativeQuantities:
    """Tests for negative quantity detection."""

    def test_no_negatives(self, clean_snapshot_1):
        issues = find_negative_quantities(clean_snapshot_1, "test")
        assert len(issues) == 0

    def test_detects_negatives(self, snapshot_with_negatives):
        issues = find_negative_quantities(snapshot_with_negatives, "test")
        assert len(issues) == 1
        assert issues[0].sku == "SKU-002"
        assert issues[0].issue_type == "negative_quantity"
        assert issues[0].severity == "error"

    def test_zero_is_not_negative(self):
        df = pd.DataFrame({
            "sku": ["SKU-001"],
            "name": ["Widget"],
            "quantity": [0],
            "location": ["WA"],
            "date": ["2024-01-01"],
        })
        issues = find_negative_quantities(df, "test")
        assert len(issues) == 0


class TestFindNullFields:
    """Tests for null/empty field detection."""

    def test_no_nulls(self, clean_snapshot_1):
        issues = find_null_fields(clean_snapshot_1, "test")
        assert len(issues) == 0

    def test_detects_null_quantity(self):
        df = pd.DataFrame({
            "sku": ["SKU-001"],
            "name": ["Widget"],
            "quantity": [None],
            "location": ["WA"],
            "date": ["2024-01-01"],
        })
        issues = find_null_fields(df, "test")
        qty_issues = [i for i in issues if i.field == "quantity"]
        assert len(qty_issues) == 1

    def test_detects_empty_name(self):
        df = pd.DataFrame({
            "sku": ["SKU-001"],
            "name": [""],
            "quantity": [100],
            "location": ["WA"],
            "date": ["2024-01-01"],
        })
        issues = find_null_fields(df, "test")
        name_issues = [i for i in issues if i.field == "name"]
        assert len(name_issues) == 1

    def test_detects_null_date(self):
        df = pd.DataFrame({
            "sku": ["SKU-001"],
            "name": ["Widget"],
            "quantity": [100],
            "location": ["WA"],
            "date": [None],
        })
        issues = find_null_fields(df, "test")
        date_issues = [i for i in issues if i.field == "date"]
        assert len(date_issues) == 1
        assert date_issues[0].severity == "error"

    def test_detects_empty_location(self):
        df = pd.DataFrame({
            "sku": ["SKU-001"],
            "name": ["Widget"],
            "quantity": [100],
            "location": [""],
            "date": ["2024-01-01"],
        })
        issues = find_null_fields(df, "test")
        loc_issues = [i for i in issues if i.field == "location"]
        assert len(loc_issues) == 1
        assert loc_issues[0].severity == "error"


class TestGetDuplicateSkus:
    """Tests for the duplicate SKU set extractor."""

    def test_no_duplicates(self, clean_snapshot_1):
        assert get_duplicate_skus(clean_snapshot_1) == set()

    def test_returns_duplicate_sku_set(self, snapshot_with_duplicates):
        assert get_duplicate_skus(snapshot_with_duplicates) == {"SKU-002"}


class TestValidateSnapshot:
    """Tests for the combined validation runner."""

    def test_clean_data_no_issues(self, clean_snapshot_1):
        issues = validate_snapshot(clean_snapshot_1, "test")
        assert len(issues) == 0

    def test_combines_all_issue_types(self, snapshot_with_duplicates):
        issues = validate_snapshot(snapshot_with_duplicates, "test")
        issue_types = {i.issue_type for i in issues}
        assert "duplicate_sku" in issue_types
        assert "negative_quantity" in issue_types

    def test_all_issues_have_snapshot_label(self, snapshot_with_duplicates):
        issues = validate_snapshot(snapshot_with_duplicates, "my_label")
        assert all(i.snapshot == "my_label" for i in issues)
