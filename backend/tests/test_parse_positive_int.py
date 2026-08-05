"""Tests for _parse_positive_int in options_analyzer."""

import pytest

from options_analyzer import _parse_positive_int


class TestParsePositiveInt:
    @pytest.mark.parametrize(
        ("field", "value", "expected"),
        [
            ("contracts", "1", 1),
            ("contracts", "100", 100),
            ("contracts", "100.0", 100),
            ("contracts", "  5  ", 5),
            ("multiplier", "50", 50),
        ],
    )
    def test_valid_values(self, field, value, expected):
        assert _parse_positive_int(value, field, 2) == expected
        assert isinstance(_parse_positive_int(value, field, 2), int)

    @pytest.mark.parametrize("field", ["contracts", "multiplier"])
    @pytest.mark.parametrize("value", ["100.5", "0", "-100", "inf", "nan"])
    def test_non_positive_or_non_integer_raises(self, field, value):
        with pytest.raises(
            ValueError,
            match=f"Row 5: {field} must be a positive integer",
        ):
            _parse_positive_int(value, field, 5)

    @pytest.mark.parametrize("field", ["contracts", "multiplier"])
    def test_non_numeric_raises(self, field):
        with pytest.raises(ValueError, match=f"Row 5: {field} 'abc' is not a number"):
            _parse_positive_int("abc", field, 5)

    def test_contracts_row_number_in_error_message(self):
        with pytest.raises(ValueError, match="Row 7: contracts"):
            _parse_positive_int("0", "contracts", 7)
