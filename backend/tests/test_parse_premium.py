"""Tests for options premium parsing in options_analyzer."""

import pytest

from options_analyzer import _parse_premium


class TestParsePremium:
    @pytest.mark.parametrize("value", [None, "", "   "])
    def test_blank_raises(self, value):
        with pytest.raises(ValueError, match="Row 3: premium is blank"):
            _parse_premium(value, 3)

    @pytest.mark.parametrize(
        ("value", "expected"),
        [
            ("$4.30", 4.30),
            ("4.30", 4.30),
            ("$1,234.56", 1234.56),
            ("1,234.56", 1234.56),
            ("0", 0.0),
            ("$0.00", 0.0),
        ],
    )
    def test_valid_values(self, value, expected):
        assert _parse_premium(value, 2) == expected
        assert isinstance(_parse_premium(value, 2), float)

    @pytest.mark.parametrize("value", ["-1", "-$5.00"])
    def test_negative_raises(self, value):
        with pytest.raises(
            ValueError, match="Row 5: premium must be non-negative, got"
        ):
            _parse_premium(value, 5)

    def test_non_numeric_raises(self):
        with pytest.raises(ValueError, match="Row 5: premium 'abc' is not a number"):
            _parse_premium("abc", 5)

    @pytest.mark.parametrize("value", ["$", "$  ", "  $  "])
    def test_dollar_only_raises_not_a_number(self, value):
        with pytest.raises(ValueError, match="Row 5: premium .* is not a number"):
            _parse_premium(value, 5)

    @pytest.mark.parametrize("value", ["inf", "nan"])
    def test_non_finite_raises(self, value):
        with pytest.raises(
            ValueError, match="Row 5: premium must be non-negative, got"
        ):
            _parse_premium(value, 5)

    def test_row_number_in_error_message(self):
        with pytest.raises(ValueError, match="Row 7:"):
            _parse_premium("-1", 7)
