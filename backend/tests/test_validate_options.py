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


class TestValidateOptionsExpiredPosition:
    @pytest.mark.parametrize(
        "open_action,close_action",
        [
            ("BTO", "OEXP"),
            ("STO", "OASGN"),
            ("BTO", "OASGN"),
            ("STO", "OEXP"),
        ],
    )
    def test_passive_close_emits_info(self, open_action, close_action):
        open_trade = _opt(action=open_action, date="2024-01-01", premium=2.5)
        close_trade = _opt(action=close_action, date="2024-01-19", premium=0.0)
        warnings = validate_options([open_trade, close_trade])
        expired = [w for w in warnings if w["type"] == "expired_position"]
        assert len(expired) == 1
        notice = expired[0]
        assert notice["level"] == "info"
        assert notice["action"] == close_action
        assert notice["underlying"] == "AAPL"
        assert notice["option_type"] == "CALL"
        assert notice["strike"] == 185.0
        assert notice["expiration"] == "2024-01-19"
        assert notice["open_date"] == "2024-01-01"
        assert notice["date"] == "2024-01-19"
        assert "Expired:" in notice["message"]
        assert "2024-01-01" in notice["message"]
        assert "2024-01-19" in notice["message"]

    def test_normal_close_does_not_emit_expired_position(self):
        open_trade = _opt(action="BTO", date="2024-01-01")
        close_trade = _opt(action="BTC", date="2024-01-10", premium=3.0)
        warnings = validate_options([open_trade, close_trade])
        assert not any(w["type"] == "expired_position" for w in warnings)

    def test_passive_close_without_open_does_not_emit_expired_position(self):
        trade = _opt(action="OEXP", date="2024-01-19", premium=0.0)
        warnings = validate_options([trade])
        assert not any(w["type"] == "expired_position" for w in warnings)
        assert any(w["type"] == "unmatched_close" for w in warnings)

    def test_one_expired_and_one_unclosed(self):
        open_expired = _opt(action="BTO", date="2024-01-01", strike=185.0)
        close_expired = _opt(
            action="OEXP", date="2024-01-19", strike=185.0, premium=0.0
        )
        open_unclosed = _opt(
            action="BTO", date="2024-01-02", strike=190.0, expiration="2024-02-16"
        )
        warnings = validate_options([open_expired, close_expired, open_unclosed])
        expired = [w for w in warnings if w["type"] == "expired_position"]
        unclosed = [w for w in warnings if w["type"] == "unclosed_position"]
        assert len(expired) == 1
        assert expired[0]["strike"] == 185.0
        assert len(unclosed) == 1
        assert unclosed[0]["strike"] == 190.0


class TestValidateOptionsNakedShort:
    def test_sto_alone_emits_naked_short(self):
        trade = _opt(action="STO", premium=1.5)
        warnings = [w for w in validate_options([trade]) if w["type"] == "naked_short"]
        assert len(warnings) == 1
        assert warnings[0]["level"] == "warning"

    def test_sto_with_matching_bto_no_warning(self):
        bto = _opt(action="BTO", date="2024-01-01")
        sto = _opt(action="STO", date="2024-01-02", premium=1.5)
        warnings = validate_options([bto, sto])
        assert not any(w["type"] == "naked_short" for w in warnings)

    def test_closed_sto_no_naked_short(self):
        open_trade = _opt(action="STO", date="2024-01-01", premium=1.5)
        close_trade = _opt(action="STC", date="2024-01-10", premium=0.5)
        warnings = validate_options([open_trade, close_trade])
        assert not any(w["type"] == "naked_short" for w in warnings)

    def test_sto_different_strike_from_bto_warns(self):
        bto = _opt(action="BTO", strike=180.0)
        sto = _opt(action="STO", strike=185.0, premium=1.5)
        warnings = [
            w for w in validate_options([bto, sto]) if w["type"] == "naked_short"
        ]
        assert len(warnings) == 1

    def test_bto_alone_no_naked_short(self):
        trade = _opt(action="BTO")
        warnings = validate_options([trade])
        assert not any(w["type"] == "naked_short" for w in warnings)

    def test_multiple_sto_one_covered_one_naked(self):
        bto = _opt(action="BTO", strike=185.0)
        covered_sto = _opt(action="STO", strike=185.0, premium=1.5)
        naked_sto = _opt(action="STO", strike=190.0, premium=2.0)
        warnings = [
            w
            for w in validate_options([bto, covered_sto, naked_sto])
            if w["type"] == "naked_short"
        ]
        assert len(warnings) == 1
        assert "190.0" in warnings[0]["message"]

    def test_naked_short_message_contains_label(self):
        trade = _opt(action="STO", premium=1.5)
        warnings = [w for w in validate_options([trade]) if w["type"] == "naked_short"]
        assert len(warnings) == 1
        assert "AAPL" in warnings[0]["message"]
        assert "STO" in warnings[0]["message"]
        assert "no offsetting long position" in warnings[0]["message"]


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
