"""Tests for calculate_options_pnl() in options_analyzer."""

import pytest

from options_analyzer import calculate_options_pnl


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


class TestCalculateOptionsPnlEmpty:
    def test_empty_list(self):
        assert calculate_options_pnl([]) == {
            "positions": [],
            "equity_curve": [],
            "total_pnl": 0.0,
        }


class TestCalculateOptionsPnlLong:
    def test_profitable_long(self):
        open_trade = _opt(action="BTO", premium=2.50)
        close_trade = _opt(action="BTC", date="2024-01-10", premium=4.00)
        result = calculate_options_pnl([open_trade, close_trade])
        assert result["total_pnl"] == 150.0
        assert len(result["positions"]) == 1
        assert result["positions"][0]["pnl"] == 150.0
        assert result["positions"][0]["side"] == "long"

    def test_loss_on_long(self):
        open_trade = _opt(action="BTO", premium=3.00)
        close_trade = _opt(action="BTC", date="2024-01-10", premium=1.00)
        result = calculate_options_pnl([open_trade, close_trade])
        assert result["total_pnl"] == -200.0
        assert result["positions"][0]["pnl"] == -200.0

    def test_break_even(self):
        open_trade = _opt(action="BTO", premium=2.50)
        close_trade = _opt(action="BTC", date="2024-01-10", premium=2.50)
        result = calculate_options_pnl([open_trade, close_trade])
        assert result["total_pnl"] == 0.0
        assert result["positions"][0]["pnl"] == 0.0

    def test_contracts_and_multiplier_scaling(self):
        open_trade = _opt(action="BTO", premium=1.00, contracts=2, multiplier=100)
        close_trade = _opt(
            action="BTC", date="2024-01-10", premium=2.00, contracts=2, multiplier=100
        )
        result = calculate_options_pnl([open_trade, close_trade])
        assert result["total_pnl"] == 200.0
        assert result["positions"][0]["contracts"] == 2
        assert result["positions"][0]["multiplier"] == 100

    @pytest.mark.parametrize("close_action", ["OEXP", "OASGN", "OEXER"])
    def test_passive_close_included(self, close_action):
        open_trade = _opt(action="BTO", premium=1.50)
        close_trade = _opt(action=close_action, date="2024-01-19", premium=0.0)
        result = calculate_options_pnl([open_trade, close_trade])
        assert len(result["positions"]) == 1
        assert result["positions"][0]["close_premium"] == 0.0
        assert result["positions"][0]["close_action"] == close_action
        assert result["total_pnl"] == -150.0

    @pytest.mark.parametrize("close_action", ["OEXP", "OASGN", "OEXER"])
    def test_bto_expires_worthless_ignores_close_premium(self, close_action):
        open_trade = _opt(action="BTO", premium=2.50)
        close_trade = _opt(action=close_action, date="2024-01-19", premium=0.99)
        result = calculate_options_pnl([open_trade, close_trade])
        assert result["total_pnl"] == -250.0
        assert result["positions"][0]["close_premium"] == 0.0
        assert result["positions"][0]["close_action"] == close_action


class TestCalculateOptionsPnlActiveClose:
    @pytest.mark.parametrize(
        ("open_action", "close_action", "expected_pnl"),
        [
            ("BTO", "BTC", -75.0),
            ("STO", "STC", 75.0),
        ],
    )
    def test_active_close_premium_not_overridden(
        self, open_action, close_action, expected_pnl
    ):
        open_trade = _opt(action=open_action, premium=2.00)
        close_trade = _opt(action=close_action, date="2024-01-10", premium=1.25)
        result = calculate_options_pnl([open_trade, close_trade])
        assert result["positions"][0]["close_premium"] == 1.25
        assert result["positions"][0]["close_action"] == close_action
        assert result["total_pnl"] == expected_pnl


class TestCalculateOptionsPnlShort:
    def test_sto_stc_profit(self):
        open_trade = _opt(action="STO", premium=1.50)
        close_trade = _opt(action="STC", date="2024-01-10", premium=0.50)
        result = calculate_options_pnl([open_trade, close_trade])
        assert result["total_pnl"] == 100.0
        assert len(result["positions"]) == 1
        assert result["positions"][0]["pnl"] == 100.0
        assert result["positions"][0]["side"] == "short"

    def test_sto_stc_loss(self):
        open_trade = _opt(action="STO", premium=1.00)
        close_trade = _opt(action="STC", date="2024-01-10", premium=1.80)
        result = calculate_options_pnl([open_trade, close_trade])
        assert result["total_pnl"] == -80.0
        assert result["positions"][0]["pnl"] == -80.0
        assert result["positions"][0]["side"] == "short"

    def test_sto_oexp_full_keep(self):
        open_trade = _opt(action="STO", premium=2.00)
        close_trade = _opt(action="OEXP", date="2024-01-19", premium=0.0)
        result = calculate_options_pnl([open_trade, close_trade])
        assert result["total_pnl"] == 200.0
        assert result["positions"][0]["close_premium"] == 0.0
        assert result["positions"][0]["close_action"] == "OEXP"
        assert result["positions"][0]["side"] == "short"

    def test_sto_oasgn_full_keep(self):
        open_trade = _opt(action="STO", premium=1.50, contracts=2)
        close_trade = _opt(action="OASGN", date="2024-01-19", premium=0.0, contracts=2)
        result = calculate_options_pnl([open_trade, close_trade])
        assert result["total_pnl"] == 300.0
        assert result["positions"][0]["close_action"] == "OASGN"
        assert result["positions"][0]["side"] == "short"

    @pytest.mark.parametrize("close_action", ["OEXP", "OASGN", "OEXER"])
    def test_sto_expires_worthless_ignores_close_premium(self, close_action):
        open_trade = _opt(action="STO", premium=2.00)
        close_trade = _opt(action=close_action, date="2024-01-19", premium=0.99)
        result = calculate_options_pnl([open_trade, close_trade])
        assert result["total_pnl"] == 200.0
        assert result["positions"][0]["close_premium"] == 0.0
        assert result["positions"][0]["close_action"] == close_action

    def test_mixed_long_and_short(self):
        long_open = _opt(action="BTO", premium=2.00)
        long_close = _opt(action="BTC", date="2024-01-10", premium=3.00)
        short_open = _opt(action="STO", date="2024-01-02", premium=1.50)
        short_close = _opt(action="STC", date="2024-01-11", premium=0.50)
        result = calculate_options_pnl([long_open, long_close, short_open, short_close])
        assert len(result["positions"]) == 2
        assert result["total_pnl"] == 200.0
        sides = {position["side"] for position in result["positions"]}
        assert sides == {"long", "short"}


class TestCalculateOptionsPnlMultiple:
    def test_multiple_long_positions_total(self):
        first_open = _opt(action="BTO", date="2024-01-01", premium=2.00)
        first_close = _opt(action="BTC", date="2024-01-10", premium=3.00)
        second_open = _opt(action="BTO", date="2024-01-02", premium=1.00)
        second_close = _opt(action="BTC", date="2024-01-11", premium=2.00)
        result = calculate_options_pnl(
            [first_open, first_close, second_open, second_close]
        )
        assert len(result["positions"]) == 2
        assert result["total_pnl"] == 200.0

    def test_total_pnl_equals_sum_of_position_pnls(self):
        first_open = _opt(action="BTO", date="2024-01-01", premium=1.00005)
        first_close = _opt(action="BTC", date="2024-01-10", premium=1.00010)
        second_open = _opt(action="BTO", date="2024-01-02", premium=1.00005)
        second_close = _opt(action="BTC", date="2024-01-11", premium=1.00010)
        result = calculate_options_pnl(
            [first_open, first_close, second_open, second_close]
        )
        position_pnls = [position["pnl"] for position in result["positions"]]
        assert result["total_pnl"] == sum(position_pnls)


class TestCalculateOptionsPnlFees:
    def test_long_open_fees_only(self):
        open_trade = _opt(action="BTO", premium=2.50, fees=1.25)
        close_trade = _opt(action="BTC", date="2024-01-10", premium=4.00)
        result = calculate_options_pnl([open_trade, close_trade])
        assert result["positions"][0]["fees"] == 1.25
        assert result["positions"][0]["pnl"] == 148.75
        assert result["total_pnl"] == 148.75

    def test_long_close_fees_only(self):
        open_trade = _opt(action="BTO", premium=2.50)
        close_trade = _opt(action="BTC", date="2024-01-10", premium=4.00, fees=0.75)
        result = calculate_options_pnl([open_trade, close_trade])
        assert result["positions"][0]["fees"] == 0.75
        assert result["positions"][0]["pnl"] == 149.25
        assert result["total_pnl"] == 149.25

    def test_long_fees_on_both_legs(self):
        open_trade = _opt(action="BTO", premium=2.50, fees=1.00)
        close_trade = _opt(action="BTC", date="2024-01-10", premium=4.00, fees=0.50)
        result = calculate_options_pnl([open_trade, close_trade])
        assert result["positions"][0]["fees"] == 1.50
        assert result["positions"][0]["pnl"] == 148.50
        assert result["total_pnl"] == 148.50

    def test_short_fees_deducted(self):
        open_trade = _opt(action="STO", premium=1.50, fees=0.65)
        close_trade = _opt(action="STC", date="2024-01-10", premium=0.50, fees=0.65)
        result = calculate_options_pnl([open_trade, close_trade])
        assert result["positions"][0]["fees"] == 1.30
        assert result["positions"][0]["pnl"] == 98.70
        assert result["total_pnl"] == 98.70

    @pytest.mark.parametrize("close_action", ["OEXP", "OASGN", "OEXER"])
    def test_passive_close_open_fees_deducted(self, close_action):
        open_trade = _opt(action="BTO", premium=1.50, fees=2.00)
        close_trade = _opt(action=close_action, date="2024-01-19", premium=0.0)
        result = calculate_options_pnl([open_trade, close_trade])
        assert result["positions"][0]["fees"] == 2.00
        assert result["positions"][0]["pnl"] == -152.00
        assert result["total_pnl"] == -152.00

    @pytest.mark.parametrize("close_action", ["OEXP", "OASGN", "OEXER"])
    def test_passive_close_close_fees_deducted(self, close_action):
        open_trade = _opt(action="BTO", premium=1.50)
        close_trade = _opt(
            action=close_action, date="2024-01-19", premium=0.0, fees=1.50
        )
        result = calculate_options_pnl([open_trade, close_trade])
        assert result["positions"][0]["fees"] == 1.50
        assert result["positions"][0]["pnl"] == -151.50
        assert result["total_pnl"] == -151.50

    def test_zero_fees_unchanged(self):
        open_trade = _opt(action="BTO", premium=2.50, fees=0.0)
        close_trade = _opt(action="BTC", date="2024-01-10", premium=4.00, fees=0.0)
        result = calculate_options_pnl([open_trade, close_trade])
        assert result["positions"][0]["fees"] == 0.0
        assert result["positions"][0]["pnl"] == 150.0
        assert result["total_pnl"] == 150.0

    def test_total_pnl_equals_sum_of_position_pnls_with_fees(self):
        first_open = _opt(action="BTO", date="2024-01-01", premium=2.00, fees=0.50)
        first_close = _opt(action="BTC", date="2024-01-10", premium=3.00, fees=0.25)
        second_open = _opt(action="STO", date="2024-01-02", premium=1.50, fees=0.75)
        second_close = _opt(action="STC", date="2024-01-11", premium=0.50, fees=0.25)
        result = calculate_options_pnl(
            [first_open, first_close, second_open, second_close]
        )
        position_pnls = [position["pnl"] for position in result["positions"]]
        assert result["total_pnl"] == sum(position_pnls)
        assert result["total_pnl"] == 198.25


class TestCalculateOptionsPnlEquityCurve:
    def test_empty_equity_curve(self):
        result = calculate_options_pnl([])
        assert result["equity_curve"] == []

    def test_single_position_equity_curve(self):
        open_trade = _opt(action="BTO", premium=2.50)
        close_trade = _opt(action="BTC", date="2024-01-10", premium=4.00)
        result = calculate_options_pnl([open_trade, close_trade])
        assert result["equity_curve"] == [
            {"date": "2024-01-10", "cumulative_pnl": 150.0}
        ]

    def test_multiple_positions_sorted_by_close_date(self):
        first_open = _opt(action="BTO", date="2024-01-01", premium=2.00)
        first_close = _opt(action="BTC", date="2024-01-10", premium=3.00)
        second_open = _opt(action="BTO", date="2024-01-02", premium=1.00)
        second_close = _opt(action="BTC", date="2024-01-05", premium=2.00)
        result = calculate_options_pnl(
            [first_open, first_close, second_open, second_close]
        )
        assert result["equity_curve"] == [
            {"date": "2024-01-05", "cumulative_pnl": 100.0},
            {"date": "2024-01-10", "cumulative_pnl": 200.0},
        ]

    def test_cumulative_pnl_accumulates(self):
        first_open = _opt(action="BTO", date="2024-01-01", premium=1.00)
        first_close = _opt(action="BTC", date="2024-01-05", premium=2.00)
        second_open = _opt(action="BTO", date="2024-01-02", premium=1.00)
        second_close = _opt(action="BTC", date="2024-01-10", premium=2.00)
        third_open = _opt(action="BTO", date="2024-01-03", premium=1.00)
        third_close = _opt(action="BTC", date="2024-01-15", premium=2.00)
        result = calculate_options_pnl(
            [
                first_open,
                first_close,
                second_open,
                second_close,
                third_open,
                third_close,
            ]
        )
        cumulative_values = [
            point["cumulative_pnl"] for point in result["equity_curve"]
        ]
        assert cumulative_values == [100.0, 200.0, 300.0]

    def test_same_close_date_multiple_positions(self):
        first_open = _opt(action="BTO", date="2024-01-01", premium=1.00)
        first_close = _opt(action="BTC", date="2024-01-10", premium=2.00)
        second_open = _opt(action="BTO", date="2024-01-02", premium=1.50)
        second_close = _opt(action="BTC", date="2024-01-10", premium=2.50)
        result = calculate_options_pnl(
            [first_open, first_close, second_open, second_close]
        )
        assert result["equity_curve"] == [
            {"date": "2024-01-10", "cumulative_pnl": 100.0},
            {"date": "2024-01-10", "cumulative_pnl": 200.0},
        ]

    def test_mixed_long_short_equity_curve(self):
        long_open = _opt(action="BTO", premium=2.00)
        long_close = _opt(action="BTC", date="2024-01-10", premium=3.00)
        short_open = _opt(action="STO", date="2024-01-02", premium=1.50)
        short_close = _opt(action="STC", date="2024-01-11", premium=2.50)
        result = calculate_options_pnl([long_open, long_close, short_open, short_close])
        assert result["equity_curve"] == [
            {"date": "2024-01-10", "cumulative_pnl": 100.0},
            {"date": "2024-01-11", "cumulative_pnl": 0.0},
        ]

    def test_equity_curve_last_point_equals_total_pnl(self):
        first_open = _opt(action="BTO", date="2024-01-01", premium=2.00, fees=0.50)
        first_close = _opt(action="BTC", date="2024-01-10", premium=3.00, fees=0.25)
        second_open = _opt(action="STO", date="2024-01-02", premium=1.50, fees=0.75)
        second_close = _opt(action="STC", date="2024-01-11", premium=0.50, fees=0.25)
        result = calculate_options_pnl(
            [first_open, first_close, second_open, second_close]
        )
        assert result["equity_curve"][-1]["cumulative_pnl"] == result["total_pnl"]

    def test_equity_curve_ends_negative(self):
        first_open = _opt(action="BTO", date="2024-01-01", premium=2.00)
        first_close = _opt(action="BTC", date="2024-01-10", premium=3.00)
        second_open = _opt(action="BTO", date="2024-01-02", premium=3.00)
        second_close = _opt(action="BTC", date="2024-01-11", premium=1.00)
        result = calculate_options_pnl(
            [first_open, first_close, second_open, second_close]
        )
        assert result["equity_curve"] == [
            {"date": "2024-01-10", "cumulative_pnl": 100.0},
            {"date": "2024-01-11", "cumulative_pnl": -100.0},
        ]
        assert result["total_pnl"] == -100.0
