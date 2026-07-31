"""Tests for options CSV sanitisation via sanitize_options_csv."""

import pytest

from options_analyzer import sanitize_options_csv

_OPTIONS_HEADER = (
    "date,underlying,option_type,action,strike,expiration,contracts,premium"
)
_CLEAN_OPTIONS_ROW = "2024-01-15,AAPL,CALL,BTO,190.00,2024-02-16,2,3.50"


class TestSanitizeOptionsCsv:
    def test_formula_injection_blocked(self):
        with pytest.raises(ValueError):
            sanitize_options_csv(
                f'{_OPTIONS_HEADER}\n2024-01-15,=HYPERLINK("evil.com"),CALL,BTO,190.00,2024-02-16,2,3.50'
            )

    def test_null_byte_blocked(self):
        with pytest.raises(ValueError, match="null bytes"):
            sanitize_options_csv(
                f"{_OPTIONS_HEADER}\n2024-01-01,AAPL\x00,CALL,BTO,190.00,2024-02-16,2,3.50"
            )

    def test_binary_blocked(self):
        with pytest.raises(ValueError):
            sanitize_options_csv("\x7fELFsomedata")

    def test_returns_string(self):
        result = sanitize_options_csv(f"{_OPTIONS_HEADER}\n{_CLEAN_OPTIONS_ROW}\n")
        assert isinstance(result, str)

    def test_bom_stripped(self):
        result = sanitize_options_csv(f"\ufeff{_OPTIONS_HEADER}\n{_CLEAN_OPTIONS_ROW}")
        assert not result.startswith("\ufeff")

    def test_crlf_normalised(self):
        result = sanitize_options_csv(f"{_OPTIONS_HEADER}\r\n{_CLEAN_OPTIONS_ROW}\r\n")
        assert "\r" not in result

    def test_cr_only_normalised(self):
        result = sanitize_options_csv(f"{_OPTIONS_HEADER}\r{_CLEAN_OPTIONS_ROW}\r")
        assert "\r" not in result

    def test_semicolons_converted(self):
        result = sanitize_options_csv(
            "date;underlying;option_type;action;strike;expiration;contracts;premium\n"
            "2024-01-15;AAPL;CALL;BTO;190.00;2024-02-16;2;3.50"
        )
        assert ";" not in result
        assert _OPTIONS_HEADER in result

    def test_clean_options_csv_unchanged(self):
        raw = f"{_OPTIONS_HEADER}\n{_CLEAN_OPTIONS_ROW}\n"
        result = sanitize_options_csv(raw)
        assert result == raw
