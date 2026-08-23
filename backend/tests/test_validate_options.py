"""Tests for validate_options() in options_analyzer."""

import pytest

from options_analyzer import validate_options


def _opt(
    date="2024-01-01",
    underlying="AAPL",
    option_type="CALL",
    action="BTO",
    strike=185.0,
    expiration="2024-01-19",
    contracts=1,
    premium=2.50,
    multiplier=100,
    fees=0.0,
):
    return {
        "date": date,
        "underlying": underlying,
        "option_type": option_type,
        "action": action,
        "strike": strike,
        "expiration": expiration,
        "contracts": contracts,
        "premium": premium,
        "multiplier": multiplier,
        "fees": fees,
    }


class TestValidateOptionsEmpty:
    def test_empty_list_returns_no_warnings(self):
        assert validate_options([]) == []


class TestValidateOptionsDuplicates:
    def test_duplicate_trade_emits_warning(self):
        trade = _opt()
        warnings = validate_options([trade, trade])
        dupes = [w for w in warnings if w["type"] == "duplicate"]
        assert len(dupes) == 1
        assert dupes[0]["level"] == "warning"
        assert "appears 2 times" in dupes[0]["message"]

    def test_different_trades_no_duplicate_warning(self):
        open_trade = _opt(action="BTO", date="2024-01-01")
        close_trade = _opt(action="BTC", date="2024-01-10", premium=3.0)
        warnings = validate_options([open_trade, close_trade])
        assert not any(w["type"] == "duplicate" for w in warnings)

    def test_three_duplicates_one_warning_with_count(self):
        trade = _opt()
        warnings = [
            w
            for w in validate_options([trade, trade, trade])
            if w["type"] == "duplicate"
        ]
        assert len(warnings) == 1
        assert "appears 3 times" in warnings[0]["message"]

    def test_duplicate_key_includes_strike_and_expiration(self):
        trade1 = _opt(strike=185.0, expiration="2024-01-19")
        trade2 = _opt(strike=190.0, expiration="2024-01-19")
        warnings = validate_options([trade1, trade2])
        assert not any(w["type"] == "duplicate" for w in warnings)


class TestValidateOptionsUnmatchedClose:
    @pytest.mark.parametrize("action", ["BTC", "STC", "OEXP", "OASGN"])
    def test_close_without_open_emits_warning(self, action):
        premium = 0.0 if action in {"OEXP", "OASGN"} else 3.0
        trade = _opt(action=action, premium=premium)
        warnings = validate_options([trade])
        unmatched = [w for w in warnings if w["type"] == "unmatched_close"]
        assert len(unmatched) == 1
        assert unmatched[0]["level"] == "warning"
        assert action in unmatched[0]["message"]
        assert "has no preceding open" in unmatched[0]["message"]

    def test_open_then_close_no_warnings(self):
        open_trade = _opt(action="BTO", date="2024-01-01")
        close_trade = _opt(action="BTC", date="2024-01-10", premium=3.0)
        assert validate_options([open_trade, close_trade]) == []

    def test_sto_open_then_stc_close_no_warnings(self):
        open_trade = _opt(action="STO", date="2024-01-01", premium=1.5)
        close_trade = _opt(action="STC", date="2024-01-10", premium=0.5)
        assert validate_options([open_trade, close_trade]) == []

    def test_lowercase_close_action_triggers_unmatched_close(self):
        trade = _opt(action="btc", premium=3.0)
        warnings = validate_options([trade])
        unmatched = [w for w in warnings if w["type"] == "unmatched_close"]
        assert len(unmatched) == 1
        assert "BTC" in unmatched[0]["message"]


class TestValidateOptionsUnclosedPosition:
    def test_open_without_close_emits_info(self):
        trade = _opt(action="BTO")
        warnings = validate_options([trade])
        unclosed = [w for w in warnings if w["type"] == "unclosed_position"]
        assert len(unclosed) == 1
        assert unclosed[0]["level"] == "info"
        assert unclosed[0]["underlying"] == "AAPL"
        assert unclosed[0]["option_type"] == "CALL"
        assert unclosed[0]["strike"] == 185.0
        assert unclosed[0]["expiration"] == "2024-01-19"
        assert "no matching close yet" in unclosed[0]["message"]


class TestValidateOptionsInvalidValues:
    def test_invalid_contracts(self):
        trade = _opt(contracts=0)
        warnings = validate_options([trade])
        assert any(w["type"] == "invalid_contracts" for w in warnings)

    def test_invalid_premium_negative(self):
        trade = _opt(premium=-1.0)
        warnings = validate_options([trade])
        assert any(w["type"] == "invalid_premium" for w in warnings)

    def test_invalid_strike(self):
        trade = _opt(strike=0)
        warnings = validate_options([trade])
        assert any(w["type"] == "invalid_strike" for w in warnings)

    def test_invalid_multiplier(self):
        trade = _opt(multiplier=0)
        warnings = validate_options([trade])
        assert any(w["type"] == "invalid_multiplier" for w in warnings)

    def test_invalid_fees(self):
        trade = _opt(fees=-0.5)
        warnings = validate_options([trade])
        assert any(w["type"] == "invalid_fees" for w in warnings)

    @pytest.mark.parametrize("action", ["OEXP", "OASGN"])
    def test_passive_close_nonzero_premium_warns(self, action):
        open_trade = _opt(action="STO", date="2024-01-01", premium=1.5)
        close_trade = _opt(action=action, date="2024-01-19", premium=1.0)
        warnings = validate_options([open_trade, close_trade])
        premium_warnings = [w for w in warnings if w["type"] == "invalid_premium"]
        assert len(premium_warnings) == 1
        assert "should have premium 0" in premium_warnings[0]["message"]
        assert not any(w["type"] == "unmatched_close" for w in warnings)
