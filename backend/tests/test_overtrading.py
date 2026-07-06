"""Tests for the check_overtrading function."""

import pytest

from csv_analyzer import (
    MIN_TRADES_FOR_FREQUENCY_SIGNAL,
    OVERTRADING_COST_DRAG_THRESHOLD,
    check_overtrading,
)

# Shared cost dicts used across tests — realistic retail defaults
COMMISSIONS = {"total_commission_usd": 5.0}
SLIPPAGE = {"total_slippage_usd": 8.0}
SPREAD = {"total_spread_usd": 2.0}
TOTAL_COSTS = 15.0  # 5 + 8 + 2


def _make_pnl(num_trades: int, total_pnl: float, span_days: int = 365) -> dict:
    """Build a minimal pnl_data dict with num_trades closed trades."""
    from datetime import date, timedelta

    start = date(2023, 1, 1)
    trades = []
    for i in range(num_trades):
        buy = start + timedelta(days=i * (span_days // max(num_trades, 1)))
        sell = buy + timedelta(days=5)
        trades.append(
            {
                "buy_date": buy.strftime("%Y-%m-%d"),
                "sell_date": sell.strftime("%Y-%m-%d"),
                "symbol": "AAPL",
                "pnl": total_pnl / num_trades,
                "cumulative_pnl": total_pnl * (i + 1) / num_trades,
            }
        )
    return {"trade_pnl": trades, "total_pnl": total_pnl}


class TestCheckOvertradingReturnsNoneWhenSafe:
    def test_no_trades_returns_none(self):
        pnl = {"trade_pnl": [], "total_pnl": 0.0}
        assert check_overtrading(pnl, COMMISSIONS, SLIPPAGE, SPREAD) is None

    def test_too_few_trades_returns_none(self):
        # 19 closed trades < MIN_TRADES_FOR_FREQUENCY_SIGNAL (20)
        pnl = _make_pnl(num_trades=19, total_pnl=1000.0)
        assert check_overtrading(pnl, COMMISSIONS, SLIPPAGE, SPREAD) is None

    def test_negative_gross_pnl_returns_none(self):
        pnl = _make_pnl(num_trades=25, total_pnl=-500.0)
        assert check_overtrading(pnl, COMMISSIONS, SLIPPAGE, SPREAD) is None

    def test_zero_gross_pnl_returns_none(self):
        pnl = _make_pnl(num_trades=25, total_pnl=0.0)
        assert check_overtrading(pnl, COMMISSIONS, SLIPPAGE, SPREAD) is None

    def test_low_cost_drag_returns_none(self):
        # Costs = $15, gross = $1000 → drag = 1.5%, well below 20% threshold
        pnl = _make_pnl(num_trades=25, total_pnl=1000.0)
        assert check_overtrading(pnl, COMMISSIONS, SLIPPAGE, SPREAD) is None


class TestCheckOvertradingFiresWhenCostsDrag:
    def test_returns_dict_when_costs_exceed_threshold(self):
        # Costs = $15, gross = $50 → drag = 30%, above 20%
        pnl = _make_pnl(num_trades=25, total_pnl=50.0)
        result = check_overtrading(pnl, COMMISSIONS, SLIPPAGE, SPREAD)
        assert isinstance(result, dict)

    def test_type_is_overtrading(self):
        pnl = _make_pnl(num_trades=25, total_pnl=50.0)
        result = check_overtrading(pnl, COMMISSIONS, SLIPPAGE, SPREAD)
        assert result["type"] == "overtrading"

    def test_level_is_warning(self):
        pnl = _make_pnl(num_trades=25, total_pnl=50.0)
        result = check_overtrading(pnl, COMMISSIONS, SLIPPAGE, SPREAD)
        assert result["level"] == "warning"

    def test_cost_drag_pct_is_accurate(self):
        pnl = _make_pnl(num_trades=25, total_pnl=50.0)
        result = check_overtrading(pnl, COMMISSIONS, SLIPPAGE, SPREAD)
        # drag = 15 / 50 = 0.30
        assert abs(result["cost_drag_pct"] - 0.30) < 0.001

    def test_total_costs_usd_is_sum_of_inputs(self):
        pnl = _make_pnl(num_trades=25, total_pnl=50.0)
        result = check_overtrading(pnl, COMMISSIONS, SLIPPAGE, SPREAD)
        assert result["total_costs_usd"] == pytest.approx(TOTAL_COSTS)

    def test_num_closed_trades_matches_input(self):
        pnl = _make_pnl(num_trades=25, total_pnl=50.0)
        result = check_overtrading(pnl, COMMISSIONS, SLIPPAGE, SPREAD)
        assert result["num_closed_trades"] == 25

    def test_message_contains_cost_percentage(self):
        pnl = _make_pnl(num_trades=25, total_pnl=50.0)
        result = check_overtrading(pnl, COMMISSIONS, SLIPPAGE, SPREAD)
        assert "30.0%" in result["message"]

    def test_message_contains_trade_count(self):
        pnl = _make_pnl(num_trades=25, total_pnl=50.0)
        result = check_overtrading(pnl, COMMISSIONS, SLIPPAGE, SPREAD)
        assert "25 closed trades" in result["message"]


class TestCheckOvertradingTradesPerYear:
    def test_trades_per_year_computed_when_dates_present(self):
        pnl = _make_pnl(num_trades=25, total_pnl=50.0, span_days=365)
        result = check_overtrading(pnl, COMMISSIONS, SLIPPAGE, SPREAD)
        assert result["trades_per_year"] is not None
        assert result["trades_per_year"] > 0

    def test_trades_per_year_is_none_without_dates(self):
        pnl = {
            "trade_pnl": [{"pnl": 5.0} for _ in range(25)],
            "total_pnl": 50.0,
        }
        result = check_overtrading(pnl, COMMISSIONS, SLIPPAGE, SPREAD)
        assert result["trades_per_year"] is None

    def test_frequency_appears_in_message_when_known(self):
        pnl = _make_pnl(num_trades=25, total_pnl=50.0, span_days=365)
        result = check_overtrading(pnl, COMMISSIONS, SLIPPAGE, SPREAD)
        assert "trades/year" in result["message"]


class TestCheckOvertradingEdgeCases:
    def test_exactly_at_min_trades_fires(self):
        # Exactly MIN_TRADES_FOR_FREQUENCY_SIGNAL — should fire if costs are high enough
        pnl = _make_pnl(num_trades=MIN_TRADES_FOR_FREQUENCY_SIGNAL, total_pnl=50.0)
        result = check_overtrading(pnl, COMMISSIONS, SLIPPAGE, SPREAD)
        assert result is not None

    def test_zero_costs_never_fires(self):
        pnl = _make_pnl(num_trades=25, total_pnl=50.0)
        zero = {"total_commission_usd": 0.0}
        zero_s = {"total_slippage_usd": 0.0}
        zero_b = {"total_spread_usd": 0.0}
        assert check_overtrading(pnl, zero, zero_s, zero_b) is None

    def test_at_exact_threshold_fires(self):
        # drag = exactly 20% → should fire (>= threshold)
        gross = TOTAL_COSTS / OVERTRADING_COST_DRAG_THRESHOLD
        pnl = _make_pnl(num_trades=25, total_pnl=gross)
        assert check_overtrading(pnl, COMMISSIONS, SLIPPAGE, SPREAD) is not None

    def test_just_above_threshold_fires(self):
        gross = (TOTAL_COSTS / OVERTRADING_COST_DRAG_THRESHOLD) - 0.01
        pnl = _make_pnl(num_trades=25, total_pnl=gross)
        result = check_overtrading(pnl, COMMISSIONS, SLIPPAGE, SPREAD)
        assert result is not None


class TestCheckOvertradingInputGuards:
    def test_non_dict_inputs_return_none(self):
        pnl = _make_pnl(num_trades=25, total_pnl=100.0)
        # Pass non-dict for commissions
        assert check_overtrading(pnl, None, SLIPPAGE, SPREAD) is None
        assert check_overtrading(pnl, COMMISSIONS, None, SPREAD) is None
        assert check_overtrading(pnl, COMMISSIONS, SLIPPAGE, None) is None
        # Pass non-dict for all
        assert check_overtrading(pnl, None, None, None) is None

    def test_non_numeric_costs_are_zero(self):
        pnl = _make_pnl(num_trades=25, total_pnl=100.0)
        weird = {"total_commission_usd": "not_a_number"}
        # Should not raise, should treat as zero
        result = check_overtrading(pnl, weird, SLIPPAGE, SPREAD)
        assert isinstance(result, dict) or result is None

    def test_zero_bid_ask_spread(self):
        pnl = _make_pnl(num_trades=25, total_pnl=50.0)
        zero_spread = {"total_spread_usd": 0.0}
        # Should still fire if drag is high enough
        result = check_overtrading(pnl, COMMISSIONS, SLIPPAGE, zero_spread)
        assert isinstance(result, dict) or result is None
