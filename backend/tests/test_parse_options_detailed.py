"""Tests for parse_options_detailed() in options_analyzer."""

import pytest

from options_analyzer import (
    DEFAULT_CONTRACT_MULTIPLIER,
    FREE_TIER_OPTIONS_ROW_LIMIT,
    OptionsFreeTierLimitExceeded,
    parse_options_detailed,
)

_OPTIONS_HEADER = (
    "date,underlying,option_type,action,strike,expiration,contracts,premium\n"
)

VALID_CSV = (
    _OPTIONS_HEADER
    + "2024-01-15,AAPL,CALL,BTO,185.50,2024-06-21,2,3.25\n"
    + "2024-02-20,MSFT,PUT,STC,400.00,2024-03-15,1,1.50\n"
)


def _make_options_csv(num_rows: int) -> str:
    rows = "".join(
        f"2024-01-{(i % 28) + 1:02d},AAPL,CALL,BTO,100.00,2024-06-21,1,2.50\n"
        for i in range(num_rows)
    )
    return _OPTIONS_HEADER + rows


class TestParseOptionsDetailedHappyPath:
    def test_returns_list(self):
        result = parse_options_detailed(VALID_CSV)
        assert isinstance(result, list)

    def test_correct_row_count(self):
        result = parse_options_detailed(VALID_CSV)
        assert len(result) == 2

    def test_date_preserved_as_string(self):
        result = parse_options_detailed(VALID_CSV)
        assert result[0]["date"] == "2024-01-15"

    def test_expiration_preserved_as_string(self):
        result = parse_options_detailed(VALID_CSV)
        assert result[0]["expiration"] == "2024-06-21"

    def test_underlying_uppercased(self):
        csv_data = (
            _OPTIONS_HEADER + "2024-01-15,aapl,CALL,BTO,185.50,2024-06-21,1,3.25\n"
        )
        result = parse_options_detailed(csv_data)
        assert result[0]["underlying"] == "AAPL"

    def test_option_type_case_insensitive(self):
        csv_data = (
            _OPTIONS_HEADER
            + "2024-01-15,AAPL,call,BTO,185.50,2024-06-21,1,3.25\n"
            + "2024-02-20,MSFT,Put,STC,400.00,2024-03-15,1,1.50\n"
        )
        result = parse_options_detailed(csv_data)
        assert result[0]["option_type"] == "CALL"
        assert result[1]["option_type"] == "PUT"

    def test_action_case_insensitive(self):
        csv_data = (
            _OPTIONS_HEADER
            + "2024-01-15,AAPL,CALL,bto,185.50,2024-06-21,1,3.25\n"
            + "2024-02-20,MSFT,PUT,Stc,400.00,2024-03-15,1,1.50\n"
        )
        result = parse_options_detailed(csv_data)
        assert result[0]["action"] == "BTO"
        assert result[1]["action"] == "STC"

    def test_option_type_and_action_values(self):
        result = parse_options_detailed(VALID_CSV)
        assert result[0]["option_type"] == "CALL"
        assert result[0]["action"] == "BTO"
        assert result[1]["option_type"] == "PUT"
        assert result[1]["action"] == "STC"

    def test_strike_is_float(self):
        result = parse_options_detailed(VALID_CSV)
        assert isinstance(result[0]["strike"], float)
        assert result[0]["strike"] == 185.50

    def test_contracts_is_int(self):
        result = parse_options_detailed(VALID_CSV)
        assert isinstance(result[0]["contracts"], int)
        assert result[0]["contracts"] == 2

    def test_premium_is_float(self):
        result = parse_options_detailed(VALID_CSV)
        assert isinstance(result[0]["premium"], float)
        assert result[0]["premium"] == 3.25

    def test_header_only_returns_empty_list(self):
        result = parse_options_detailed(_OPTIONS_HEADER)
        assert result == []


class TestParseOptionsDetailedOptionalColumns:
    def test_multiplier_and_fees_parsed(self):
        csv_data = (
            "date,underlying,option_type,action,strike,expiration,contracts,premium,multiplier,fees\n"
            "2024-01-15,AAPL,CALL,BTO,185.50,2024-06-21,2,3.25,50,1.25\n"
        )
        result = parse_options_detailed(csv_data)
        assert result[0]["multiplier"] == 50
        assert result[0]["fees"] == 1.25

    def test_missing_optional_columns_use_defaults(self):
        result = parse_options_detailed(VALID_CSV)
        assert result[0]["multiplier"] == DEFAULT_CONTRACT_MULTIPLIER
        assert result[0]["fees"] == 0.0

    def test_blank_optional_columns_use_defaults(self):
        csv_data = (
            "date,underlying,option_type,action,strike,expiration,contracts,premium,multiplier,fees\n"
            "2024-01-15,AAPL,CALL,BTO,185.50,2024-06-21,2,3.25,,\n"
        )
        result = parse_options_detailed(csv_data)
        assert result[0]["multiplier"] == DEFAULT_CONTRACT_MULTIPLIER
        assert result[0]["fees"] == 0.0

    def test_fees_with_currency_symbols_parsed(self):
        csv_data = (
            "date,underlying,option_type,action,strike,expiration,contracts,premium,fees\n"
            "2024-01-15,AAPL,CALL,BTO,185.50,2024-06-21,2,3.25,$1.25\n"
        )
        result = parse_options_detailed(csv_data)
        assert result[0]["fees"] == 1.25


class TestParseOptionsDetailedColumnHandling:
    def test_mixed_case_headers(self):
        csv_data = (
            "Date,Underlying,Option_Type,Action,Strike,Expiration,Contracts,Premium\n"
            "2024-01-15,AAPL,CALL,BTO,185.50,2024-06-21,1,3.25\n"
        )
        result = parse_options_detailed(csv_data)
        assert len(result) == 1

    def test_padded_headers(self):
        csv_data = (
            " date , underlying , option_type , action , strike , expiration , contracts , premium \n"
            "2024-01-15,AAPL,CALL,BTO,185.50,2024-06-21,1,3.25\n"
        )
        result = parse_options_detailed(csv_data)
        assert len(result) == 1

    def test_extra_columns_ignored(self):
        csv_data = (
            "date,underlying,option_type,action,strike,expiration,contracts,premium,notes\n"
            "2024-01-15,AAPL,CALL,BTO,185.50,2024-06-21,1,3.25,entry\n"
        )
        result = parse_options_detailed(csv_data)
        assert len(result) == 1
        assert "notes" not in result[0]

    def test_missing_column_raises(self):
        csv_data = (
            "date,underlying,option_type,action,strike,expiration,contracts\n"
            "2024-01-15,AAPL,CALL,BTO,185.50,2024-06-21,1\n"
        )
        with pytest.raises(ValueError, match="missing required columns"):
            parse_options_detailed(csv_data)

    def test_empty_csv_raises(self):
        with pytest.raises(ValueError, match="CSV is empty or has no header row"):
            parse_options_detailed("")


class TestParseOptionsDetailedFieldValidation:
    def test_invalid_option_type_raises(self):
        csv_data = (
            _OPTIONS_HEADER + "2024-01-15,AAPL,SWING,BTO,185.50,2024-06-21,1,3.25\n"
        )
        with pytest.raises(ValueError, match="option_type 'SWING' is not CALL or PUT"):
            parse_options_detailed(csv_data)

    def test_invalid_action_raises(self):
        csv_data = (
            _OPTIONS_HEADER + "2024-01-15,AAPL,CALL,HOLD,185.50,2024-06-21,1,3.25\n"
        )
        with pytest.raises(ValueError, match="action 'HOLD' is not one of"):
            parse_options_detailed(csv_data)

    def test_blank_action_raises(self):
        csv_data = _OPTIONS_HEADER + "2024-01-15,AAPL,CALL,,185.50,2024-06-21,1,3.25\n"
        with pytest.raises(ValueError, match="Row 2: action is blank"):
            parse_options_detailed(csv_data)

    def test_zero_strike_raises(self):
        csv_data = _OPTIONS_HEADER + "2024-01-15,AAPL,CALL,BTO,0,2024-06-21,1,3.25\n"
        with pytest.raises(ValueError, match="strike must be positive"):
            parse_options_detailed(csv_data)

    def test_zero_contracts_raises(self):
        csv_data = (
            _OPTIONS_HEADER + "2024-01-15,AAPL,CALL,BTO,185.50,2024-06-21,0,3.25\n"
        )
        with pytest.raises(ValueError, match="contracts must be a positive integer"):
            parse_options_detailed(csv_data)

    def test_fractional_contracts_raises(self):
        csv_data = (
            _OPTIONS_HEADER + "2024-01-15,AAPL,CALL,BTO,185.50,2024-06-21,1.5,3.25\n"
        )
        with pytest.raises(ValueError, match="contracts must be a positive integer"):
            parse_options_detailed(csv_data)

    def test_blank_underlying_raises(self):
        csv_data = _OPTIONS_HEADER + "2024-01-15,,CALL,BTO,185.50,2024-06-21,1,3.25\n"
        with pytest.raises(ValueError, match="Row 2: underlying is blank"):
            parse_options_detailed(csv_data)

    def test_blank_contracts_raises(self):
        csv_data = (
            _OPTIONS_HEADER + "2024-01-15,AAPL,CALL,BTO,185.50,2024-06-21,,3.25\n"
        )
        with pytest.raises(ValueError, match="Row 2: contracts is blank"):
            parse_options_detailed(csv_data)

    def test_blank_premium_raises(self):
        csv_data = _OPTIONS_HEADER + "2024-01-15,AAPL,CALL,BTO,185.50,2024-06-21,1,\n"
        with pytest.raises(ValueError, match="Row 2: premium is blank"):
            parse_options_detailed(csv_data)

    def test_negative_premium_raises(self):
        csv_data = (
            _OPTIONS_HEADER + "2024-01-15,AAPL,CALL,BTO,185.50,2024-06-21,1,-1.00\n"
        )
        with pytest.raises(ValueError, match="premium must be non-negative"):
            parse_options_detailed(csv_data)

    def test_invalid_underlying_digits_only_raises(self):
        csv_data = (
            _OPTIONS_HEADER + "2024-01-15,12345,CALL,BTO,185.50,2024-06-21,1,3.25\n"
        )
        with pytest.raises(ValueError, match="underlying '12345' contains invalid"):
            parse_options_detailed(csv_data)

    def test_invalid_underlying_with_space_raises(self):
        csv_data = (
            _OPTIONS_HEADER + "2024-01-15,AA PL,CALL,BTO,185.50,2024-06-21,1,3.25\n"
        )
        with pytest.raises(ValueError, match="underlying 'AA PL' contains invalid"):
            parse_options_detailed(csv_data)

    def test_invalid_date_format_raises(self):
        csv_data = (
            _OPTIONS_HEADER + "01/15/2024,AAPL,CALL,BTO,185.50,2024-06-21,1,3.25\n"
        )
        with pytest.raises(ValueError, match="Row 2: invalid date"):
            parse_options_detailed(csv_data)

    def test_invalid_expiration_format_raises(self):
        csv_data = (
            _OPTIONS_HEADER + "2024-01-15,AAPL,CALL,BTO,185.50,06/21/2024,1,3.25\n"
        )
        with pytest.raises(ValueError, match="Row 2: invalid expiration"):
            parse_options_detailed(csv_data)

    def test_expiration_before_date_raises(self):
        csv_data = (
            _OPTIONS_HEADER + "2024-06-21,AAPL,CALL,BTO,185.50,2024-01-15,1,3.25\n"
        )
        with pytest.raises(
            ValueError,
            match="Row 2: expiration '2024-01-15' must not be before date '2024-06-21'",
        ):
            parse_options_detailed(csv_data)

    def test_expiration_equal_to_date_is_valid(self):
        csv_data = (
            _OPTIONS_HEADER + "2024-06-21,AAPL,CALL,BTO,185.50,2024-06-21,1,3.25\n"
        )
        result = parse_options_detailed(csv_data)
        assert result[0]["date"] == "2024-06-21"
        assert result[0]["expiration"] == "2024-06-21"

    def test_expiration_before_date_row_number_in_error_message(self):
        csv_data = (
            _OPTIONS_HEADER
            + "2024-01-15,AAPL,CALL,BTO,185.50,2024-06-21,1,3.25\n"
            + "2024-01-16,AAPL,CALL,BTO,185.50,2024-06-21,1,3.25\n"
            + "2024-06-21,AAPL,CALL,BTO,185.50,2024-01-15,1,3.25\n"
        )
        with pytest.raises(
            ValueError,
            match="Row 4: expiration '2024-01-15' must not be before date '2024-06-21'",
        ):
            parse_options_detailed(csv_data)

    def test_row_number_in_error_message(self):
        csv_data = (
            _OPTIONS_HEADER
            + "2024-01-15,AAPL,CALL,BTO,185.50,2024-06-21,1,3.25\n"
            + "2024-01-16,AAPL,CALL,BTO,185.50,2024-06-21,1,3.25\n"
            + "2024-01-17,AAPL,CALL,HOLD,185.50,2024-06-21,1,3.25\n"
        )
        with pytest.raises(ValueError, match="Row 4: action 'HOLD'"):
            parse_options_detailed(csv_data)


class TestParseOptionsDetailedOexpOasgn:
    def test_oexp_with_zero_premium_parses(self):
        csv_data = _OPTIONS_HEADER + "2024-01-15,AAPL,CALL,OEXP,185.50,2024-06-21,1,0\n"
        result = parse_options_detailed(csv_data)
        assert result[0]["action"] == "OEXP"
        assert result[0]["premium"] == 0.0

    def test_oasgn_with_zero_premium_parses(self):
        csv_data = _OPTIONS_HEADER + "2024-01-15,AAPL,PUT,OASGN,185.50,2024-06-21,1,0\n"
        result = parse_options_detailed(csv_data)
        assert result[0]["action"] == "OASGN"
        assert result[0]["premium"] == 0.0

    def test_oexp_with_nonzero_premium_accepted(self):
        csv_data = (
            _OPTIONS_HEADER + "2024-01-15,AAPL,CALL,OEXP,185.50,2024-06-21,1,2.50\n"
        )
        result = parse_options_detailed(csv_data)
        assert result[0]["action"] == "OEXP"
        assert result[0]["premium"] == 2.50


class TestParseOptionsDetailedBlankRows:
    def test_blank_row_in_middle_skipped(self):
        csv_data = (
            _OPTIONS_HEADER
            + "2024-01-15,AAPL,CALL,BTO,185.50,2024-06-21,1,3.25\n"
            + ",,,,,,,\n"
            + "2024-02-20,MSFT,PUT,STC,400.00,2024-03-15,1,1.50\n"
        )
        result = parse_options_detailed(csv_data)
        assert len(result) == 2


class TestParseOptionsDetailedFreeTierLimit:
    def test_over_limit_raises(self):
        with pytest.raises(
            OptionsFreeTierLimitExceeded,
            match=f"exceeds the free tier limit of {FREE_TIER_OPTIONS_ROW_LIMIT}",
        ):
            parse_options_detailed(_make_options_csv(FREE_TIER_OPTIONS_ROW_LIMIT + 1))

    def test_exactly_at_limit_does_not_raise_limit_error(self):
        result = parse_options_detailed(_make_options_csv(FREE_TIER_OPTIONS_ROW_LIMIT))
        assert len(result) == FREE_TIER_OPTIONS_ROW_LIMIT

    def test_blank_rows_after_limit_not_counted(self):
        trailing_blanks = ",,,,,,,\n,,,,,,,\n"
        result = parse_options_detailed(
            _make_options_csv(FREE_TIER_OPTIONS_ROW_LIMIT) + trailing_blanks
        )
        assert len(result) == FREE_TIER_OPTIONS_ROW_LIMIT

    def test_blank_rows_with_extra_columns_not_counted(self):
        trailing_blanks = ",,,,,,,,\n,,,,,,,,\n"
        result = parse_options_detailed(
            _make_options_csv(FREE_TIER_OPTIONS_ROW_LIMIT) + trailing_blanks
        )
        assert len(result) == FREE_TIER_OPTIONS_ROW_LIMIT

    def test_is_free_tier_false_bypasses_limit(self):
        result = parse_options_detailed(
            _make_options_csv(FREE_TIER_OPTIONS_ROW_LIMIT + 1),
            is_free_tier=False,
        )
        assert len(result) == FREE_TIER_OPTIONS_ROW_LIMIT + 1

    def test_header_only_returns_empty_list(self):
        result = parse_options_detailed(_OPTIONS_HEADER)
        assert result == []

    def test_empty_csv_raises(self):
        with pytest.raises(ValueError, match="CSV is empty or has no header row"):
            parse_options_detailed("")
