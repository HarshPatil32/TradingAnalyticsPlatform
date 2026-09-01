"""Tests for extract_assignment_exercise_events() in options_analyzer."""

import pytest

from options_analyzer import extract_assignment_exercise_events


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


class TestExtractAssignmentExerciseEventsEmpty:
    def test_empty_trades_returns_empty_list(self):
        assert extract_assignment_exercise_events([]) == []


class TestExtractAssignmentExerciseEventsValidCombos:
    @pytest.mark.parametrize(
        (
            "open_action",
            "option_type",
            "close_action",
            "equity_action",
            "expected_price",
        ),
        [
            ("BTO", "CALL", "OEXER", "BUY", 187.50),
            ("BTO", "PUT", "OEXER", "SELL", 182.50),
            ("STO", "PUT", "OASGN", "BUY", 182.50),
            ("STO", "CALL", "OASGN", "SELL", 187.50),
        ],
    )
    def test_valid_combo_emits_m_event(
        self,
        open_action,
        option_type,
        close_action,
        equity_action,
        expected_price,
    ):
        open_trade = _opt(
            action=open_action,
            option_type=option_type,
            date="2024-01-01",
            premium=2.50,
        )
        close_trade = _opt(
            action=close_action,
            option_type=option_type,
            date="2024-01-19",
            premium=0.0,
        )
        events = extract_assignment_exercise_events([open_trade, close_trade])
        assert len(events) == 1
        event = events[0]
        assert event["action"] == "M"
        assert event["symbol"] == "AAPL"
        assert event["date"] == "2024-01-19"
        assert event["shares"] == 100
        assert event["equity_action"] == equity_action
        assert event["strike"] == 185.0
        assert event["adjusted_price_per_share"] == expected_price
        assert event["total_adjusted_cost"] == round(expected_price * 100, 2)
        assert event["source"] == close_action
        assert event["option_type"] == option_type
        assert event["open_action"] == open_action
        assert event["open_date"] == "2024-01-01"
        assert event["expiration"] == "2024-01-19"
        assert event["contracts"] == 1
        assert event["multiplier"] == 100

    def test_multi_contract_scaling(self):
        open_trade = _opt(
            action="BTO",
            option_type="CALL",
            date="2024-01-01",
            premium=2.50,
            contracts=2,
            multiplier=100,
        )
        close_trade = _opt(
            action="OEXER",
            option_type="CALL",
            date="2024-01-19",
            premium=0.0,
            contracts=2,
            multiplier=100,
        )
        events = extract_assignment_exercise_events([open_trade, close_trade])
        assert len(events) == 1
        event = events[0]
        assert event["contracts"] == 2
        assert event["multiplier"] == 100
        assert event["shares"] == 200
        assert event["adjusted_price_per_share"] == 187.50
        assert event["total_adjusted_cost"] == 37500.0


class TestExtractAssignmentExerciseEventsNoMatch:
    def test_active_close_emits_no_m_events(self):
        open_trade = _opt(action="BTO", date="2024-01-01")
        close_trade = _opt(action="BTC", date="2024-01-10", premium=3.0)
        assert extract_assignment_exercise_events([open_trade, close_trade]) == []

    def test_unmatched_oasgn_emits_no_m_events(self):
        close_trade = _opt(action="OASGN", date="2024-01-19", premium=0.0)
        assert extract_assignment_exercise_events([close_trade]) == []

    def test_unmatched_oexer_emits_no_m_events(self):
        close_trade = _opt(action="OEXER", date="2024-01-19", premium=0.0)
        assert extract_assignment_exercise_events([close_trade]) == []

    def test_unrecognized_combo_emits_no_m_events(self):
        open_trade = _opt(action="BTO", date="2024-01-01", premium=2.50)
        close_trade = _opt(action="OASGN", date="2024-01-19", premium=0.0)
        assert extract_assignment_exercise_events([open_trade, close_trade]) == []

    @pytest.mark.parametrize("open_action", ["BTO", "STO"])
    def test_oexp_close_emits_no_m_events(self, open_action):
        open_trade = _opt(action=open_action, date="2024-01-01", premium=2.50)
        close_trade = _opt(action="OEXP", date="2024-01-19", premium=0.0)
        assert extract_assignment_exercise_events([open_trade, close_trade]) == []

    def test_negative_adjusted_price_emits_no_m_events(self):
        open_trade = _opt(
            action="BTO",
            option_type="PUT",
            strike=1.0,
            premium=5.0,
        )
        close_trade = _opt(
            action="OEXER", option_type="PUT", date="2024-01-19", premium=0.0
        )
        assert extract_assignment_exercise_events([open_trade, close_trade]) == []
