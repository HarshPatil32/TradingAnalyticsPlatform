"""Tests for parse_options_detailed() free-tier row limit in options_analyzer."""

import pytest

from options_analyzer import (
    FREE_TIER_OPTIONS_ROW_LIMIT,
    OptionsFreeTierLimitExceeded,
    parse_options_detailed,
)

_OPTIONS_HEADER = (
    "date,underlying,option_type,action,strike,expiration,contracts,premium\n"
)


def _make_options_csv(num_rows: int) -> str:
    rows = "".join(
        f"2024-01-{(i % 28) + 1:02d},AAPL,CALL,BTO,100.00,2024-06-21,1,2.50\n"
        for i in range(num_rows)
    )
    return _OPTIONS_HEADER + rows


class TestParseOptionsDetailedFreeTierLimit:
    def test_over_limit_raises(self):
        with pytest.raises(
            OptionsFreeTierLimitExceeded,
            match=f"exceeds the free tier limit of {FREE_TIER_OPTIONS_ROW_LIMIT}",
        ):
            parse_options_detailed(_make_options_csv(FREE_TIER_OPTIONS_ROW_LIMIT + 1))

    def test_exactly_at_limit_does_not_raise_limit_error(self):
        with pytest.raises(NotImplementedError):
            parse_options_detailed(_make_options_csv(FREE_TIER_OPTIONS_ROW_LIMIT))

    def test_blank_rows_after_limit_not_counted(self):
        trailing_blanks = ",,,,,,,\n,,,,,,,\n"
        with pytest.raises(NotImplementedError):
            parse_options_detailed(
                _make_options_csv(FREE_TIER_OPTIONS_ROW_LIMIT) + trailing_blanks
            )

    def test_blank_rows_with_extra_columns_not_counted(self):
        # DictReader stores overflow fields under None as a list; must not crash.
        trailing_blanks = ",,,,,,,,\n,,,,,,,,\n"
        with pytest.raises(NotImplementedError):
            parse_options_detailed(
                _make_options_csv(FREE_TIER_OPTIONS_ROW_LIMIT) + trailing_blanks
            )

    def test_is_free_tier_false_bypasses_limit(self):
        with pytest.raises(NotImplementedError):
            parse_options_detailed(
                _make_options_csv(FREE_TIER_OPTIONS_ROW_LIMIT + 1),
                is_free_tier=False,
            )

    def test_header_only_raises_not_implemented(self):
        with pytest.raises(NotImplementedError):
            parse_options_detailed(_OPTIONS_HEADER)

    def test_empty_csv_raises(self):
        with pytest.raises(ValueError, match="CSV is empty or has no header row"):
            parse_options_detailed("")
