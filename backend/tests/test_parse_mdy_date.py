"""Tests for _parse_mdy_date() in csv_analyzer."""

import pytest

from csv_analyzer import _parse_mdy_date


class TestParseMdyDate:
    @pytest.mark.parametrize(
        ("raw_date", "expected"),
        [
            ("1/19/2024", "2024-01-19"),
            ("12/31/2024", "2024-12-31"),
            ("1/2/2024", "2024-01-02"),
            ("  1/19/2024  ", "2024-01-19"),
        ],
    )
    def test_valid_dates(self, raw_date, expected):
        assert _parse_mdy_date(raw_date) == expected

    @pytest.mark.parametrize(
        "raw_date",
        [
            "",
            "   ",
            "not-a-date",
            "13/1/2024",
            "2/30/2024",
            "2024-01-19",
        ],
    )
    def test_invalid_dates_return_none(self, raw_date):
        assert _parse_mdy_date(raw_date) is None
