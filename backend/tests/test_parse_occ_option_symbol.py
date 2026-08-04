"""Tests for _parse_occ_option_symbol() in options_analyzer."""

import pytest

from options_analyzer import _parse_occ_option_symbol


class TestParseOccOptionSymbol:
    def test_strictly_padded_happy_path(self):
        result = _parse_occ_option_symbol("AAPL  240119C00185000")
        assert result == {
            "underlying": "AAPL",
            "option_type": "CALL",
            "strike": "185.00",
            "expiration": "2024-01-19",
        }

    def test_unpadded_happy_path(self):
        result = _parse_occ_option_symbol("AAPL240119C00185000")
        assert result == {
            "underlying": "AAPL",
            "option_type": "CALL",
            "strike": "185.00",
            "expiration": "2024-01-19",
        }

    @pytest.mark.parametrize(
        "symbol",
        [
            "  AAPL  240119C00185000  ",
            "AAPL\t240119C00185000",
            "AAPL    240119C00185000",
        ],
    )
    def test_irregular_whitespace(self, symbol):
        result = _parse_occ_option_symbol(symbol)
        assert result == {
            "underlying": "AAPL",
            "option_type": "CALL",
            "strike": "185.00",
            "expiration": "2024-01-19",
        }

    @pytest.mark.parametrize(
        ("symbol", "expected_type"),
        [
            ("AAPL240119P00185000", "PUT"),
            ("AAPL240119p00185000", "PUT"),
        ],
    )
    def test_put_option_type(self, symbol, expected_type):
        result = _parse_occ_option_symbol(symbol)
        assert result is not None
        assert result["option_type"] == expected_type

    def test_lowercase_root_and_type(self):
        result = _parse_occ_option_symbol("aapl240119p00185000")
        assert result == {
            "underlying": "AAPL",
            "option_type": "PUT",
            "strike": "185.00",
            "expiration": "2024-01-19",
        }

    def test_root_with_period(self):
        result = _parse_occ_option_symbol("BRK.B 240119C00350000")
        assert result == {
            "underlying": "BRK.B",
            "option_type": "CALL",
            "strike": "350.00",
            "expiration": "2024-01-19",
        }

    def test_fractional_strike(self):
        result = _parse_occ_option_symbol("AAPL240119C00000500")
        assert result is not None
        assert result["strike"] == "0.50"

    def test_three_decimal_strike(self):
        result = _parse_occ_option_symbol("AAPL240119C00185005")
        assert result is not None
        assert result["strike"] == "185.005"

    def test_invalid_date_feb_30(self):
        assert _parse_occ_option_symbol("AAPL240230C00185000") is None

    def test_invalid_month_13(self):
        assert _parse_occ_option_symbol("AAPL241301C00185000") is None

    def test_bad_type_character(self):
        assert _parse_occ_option_symbol("AAPL240119X00185000") is None

    @pytest.mark.parametrize(
        "symbol",
        [
            "240119C00185000",
            "short",
            "",
            "   ",
        ],
    )
    def test_too_short_or_empty_root(self, symbol):
        assert _parse_occ_option_symbol(symbol) is None

    def test_non_digit_in_date(self):
        assert _parse_occ_option_symbol("AAPL24O119C00185000") is None

    def test_non_digit_in_strike(self):
        assert _parse_occ_option_symbol("AAPL240119C00185O00") is None

    def test_robinhood_style_description_returns_none(self):
        assert _parse_occ_option_symbol("AAPL 1/19/2024 Call $185.00") is None
