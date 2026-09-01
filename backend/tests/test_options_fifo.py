"""Tests for match_options_fifo() and ContractKey in options_analyzer."""

import pytest

from options_analyzer import ContractKey, match_options_fifo


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


class TestContractKey:
    def test_position_key_fields(self):
        key = ContractKey("AAPL", "CALL", 185.0, "2024-01-19")
        assert key.underlying == "AAPL"
        assert key.option_type == "CALL"
        assert key.strike == 185.0
        assert key.expiration == "2024-01-19"
        assert key == ("AAPL", "CALL", 185.0, "2024-01-19")


class TestMatchOptionsFifoEmpty:
    def test_empty_list(self):
        result = match_options_fifo([])
        assert result.matched == []
        assert result.unmatched_closes == []
        assert result.unclosed_opens == []


class TestMatchOptionsFifoSingleLeg:
    def test_single_bto_unclosed(self):
        trade = _opt(action="BTO")
        result = match_options_fifo([trade])
        assert result.matched == []
        assert result.unmatched_closes == []
        assert result.unclosed_opens == [trade]

    def test_single_btc_unmatched(self):
        trade = _opt(action="BTC", premium=3.0)
        result = match_options_fifo([trade])
        assert result.matched == []
        assert result.unmatched_closes == [trade]
        assert result.unclosed_opens == []


class TestMatchOptionsFifoPairing:
    def test_bto_then_btc_matched(self):
        open_trade = _opt(action="BTO", date="2024-01-01")
        close_trade = _opt(action="BTC", date="2024-01-10", premium=3.0)
        result = match_options_fifo([open_trade, close_trade])
        assert result.matched == [(open_trade, close_trade)]
        assert result.unmatched_closes == []
        assert result.unclosed_opens == []

    def test_sto_then_stc_matched(self):
        open_trade = _opt(action="STO", date="2024-01-01", premium=1.5)
        close_trade = _opt(action="STC", date="2024-01-10", premium=0.5)
        result = match_options_fifo([open_trade, close_trade])
        assert result.matched == [(open_trade, close_trade)]
        assert result.unclosed_opens == []


class TestMatchOptionsFifoOrdering:
    def test_two_opens_one_close_fifo(self):
        first_open = _opt(action="BTO", date="2024-01-01")
        second_open = _opt(action="BTO", date="2024-01-02")
        close_trade = _opt(action="BTC", date="2024-01-10", premium=3.0)
        result = match_options_fifo([first_open, second_open, close_trade])
        assert result.matched == [(first_open, close_trade)]
        assert result.unclosed_opens == [second_open]

    def test_two_closes_one_open_second_unmatched(self):
        open_trade = _opt(action="BTO", date="2024-01-01")
        first_close = _opt(action="BTC", date="2024-01-10", premium=3.0)
        second_close = _opt(action="BTC", date="2024-01-11", premium=3.5)
        result = match_options_fifo([open_trade, first_close, second_close])
        assert result.matched == [(open_trade, first_close)]
        assert result.unmatched_closes == [second_close]
        assert result.unclosed_opens == []


class TestMatchOptionsFifoContractKey:
    def test_different_strikes_independent(self):
        open_a = _opt(action="BTO", strike=185.0)
        close_b = _opt(action="BTC", strike=190.0, premium=3.0)
        result = match_options_fifo([open_a, close_b])
        assert result.matched == []
        assert result.unclosed_opens == [open_a]
        assert result.unmatched_closes == [close_b]

    def test_call_and_put_independent(self):
        call_open = _opt(action="BTO", option_type="CALL")
        put_close = _opt(action="BTC", option_type="PUT", premium=3.0)
        result = match_options_fifo([call_open, put_close])
        assert result.matched == []
        assert result.unclosed_opens == [call_open]
        assert result.unmatched_closes == [put_close]


class TestMatchOptionsFifoPassiveClose:
    @pytest.mark.parametrize("close_action", ["OEXP", "OASGN", "OEXER"])
    def test_passive_close_matched(self, close_action):
        open_trade = _opt(action="BTO", date="2024-01-01")
        close_trade = _opt(action=close_action, date="2024-01-19", premium=0.0)
        result = match_options_fifo([open_trade, close_trade])
        assert result.matched == [(open_trade, close_trade)]


class TestMatchOptionsFifoActionNormalization:
    def test_lowercase_close_action(self):
        open_trade = _opt(action="BTO", date="2024-01-01")
        close_trade = _opt(action="btc", date="2024-01-10", premium=3.0)
        result = match_options_fifo([open_trade, close_trade])
        assert result.matched == [(open_trade, close_trade)]
