"""Tests for options contract multiplier parsing in options_analyzer."""

import pytest

from options_analyzer import DEFAULT_CONTRACT_MULTIPLIER, _parse_multiplier


class TestParseMultiplier:
    def test_none_defaults_to_100(self):
        assert _parse_multiplier(None, 2) == DEFAULT_CONTRACT_MULTIPLIER
        assert isinstance(_parse_multiplier(None, 2), int)

    @pytest.mark.parametrize("value", ["", "   "])
    def test_blank_defaults_to_100(self, value):
        assert _parse_multiplier(value, 2) == DEFAULT_CONTRACT_MULTIPLIER

    @pytest.mark.parametrize(
        ("value", "expected"),
        [
            ("100", 100),
            ("50", 50),
            ("100.0", 100),
            ("  100  ", 100),
        ],
    )
    def test_valid_override(self, value, expected):
        assert _parse_multiplier(value, 2) == expected
        assert isinstance(_parse_multiplier(value, 2), int)

    @pytest.mark.parametrize(
        "value",
        ["100.5", "0", "-100", "inf", "nan"],
    )
    def test_non_positive_or_non_integer_raises(self, value):
        with pytest.raises(
            ValueError, match="Row 5: multiplier must be a positive integer"
        ):
            _parse_multiplier(value, 5)

    def test_non_numeric_raises(self):
        with pytest.raises(ValueError, match="Row 5: multiplier 'abc' is not a number"):
            _parse_multiplier("abc", 5)

    def test_row_number_in_error_message(self):
        with pytest.raises(ValueError, match="Row 7:"):
            _parse_multiplier("0", 7)
