"""Tests for aggregate_options_total_costs."""

import math

import pytest

import options_costs

COMMISSIONS = {"total_commission_usd": 5.0}
SLIPPAGE = {"total_slippage_usd": 8.0}
SPREAD = {"total_spread_usd": 2.0}
REGULATORY = {"total_regulatory_fees_usd": 1.5}


def _pnl(total_pnl: float, num_trades: int = 3) -> dict:
    trades = [{"symbol": "SPY", "pnl": total_pnl / max(num_trades, 1)}] * num_trades
    return {"trade_pnl": trades, "total_pnl": total_pnl}


class TestAggregateOptionsTotalCostsHappyPath:
    def test_sums_components_and_cost_drag(self):
        result = options_costs.aggregate_options_total_costs(
            _pnl(50.0), COMMISSIONS, SLIPPAGE, SPREAD
        )
        assert result["total_costs_usd"] == 15.0
        assert result["cost_drag_pct"] == 0.3
        assert result["gross_profit_usd"] == 50.0
        assert result["num_closed_trades"] == 3
        assert result["components_usd"] == {
            "commission": 5.0,
            "slippage": 8.0,
            "spread": 2.0,
            "regulatory_fees": 0.0,
        }

    def test_includes_regulatory_fees_when_provided(self):
        result = options_costs.aggregate_options_total_costs(
            _pnl(100.0), COMMISSIONS, SLIPPAGE, SPREAD, regulatory_fees=REGULATORY
        )
        assert result["total_costs_usd"] == 16.5
        assert result["components_usd"]["regulatory_fees"] == 1.5
        assert result["cost_drag_pct"] == 0.165


class TestAggregateOptionsTotalCostsEdgeCases:
    def test_empty_trade_pnl_zero_gross(self):
        pnl = {"trade_pnl": [], "total_pnl": 0.0}
        result = options_costs.aggregate_options_total_costs(
            pnl, COMMISSIONS, SLIPPAGE, SPREAD
        )
        assert result["total_costs_usd"] == 15.0
        assert result["cost_drag_pct"] is None
        assert result["num_closed_trades"] == 0

    def test_negative_gross_profit(self):
        result = options_costs.aggregate_options_total_costs(
            _pnl(-10.0), COMMISSIONS, SLIPPAGE, SPREAD
        )
        assert result["total_costs_usd"] == 15.0
        assert result["cost_drag_pct"] is None
        assert result["gross_profit_usd"] == -10.0

    def test_zero_gross_profit(self):
        result = options_costs.aggregate_options_total_costs(
            _pnl(0.0), COMMISSIONS, SLIPPAGE, SPREAD
        )
        assert result["cost_drag_pct"] is None

    def test_missing_keys_in_cost_dicts(self):
        result = options_costs.aggregate_options_total_costs(
            _pnl(50.0), {}, {}, {}
        )
        assert result["total_costs_usd"] == 0.0
        assert result["cost_drag_pct"] == 0.0

    def test_non_dict_cost_arg_treated_as_zero(self):
        result = options_costs.aggregate_options_total_costs(
            _pnl(50.0), COMMISSIONS, "bad", SPREAD
        )
        assert result["total_costs_usd"] == 7.0
        assert result["components_usd"]["slippage"] == 0.0

    def test_non_numeric_cost_string(self):
        result = options_costs.aggregate_options_total_costs(
            _pnl(50.0),
            {"total_commission_usd": "nope"},
            SLIPPAGE,
            SPREAD,
        )
        assert result["components_usd"]["commission"] == 0.0
        assert result["total_costs_usd"] == 10.0

    def test_nan_and_inf_cost_values(self):
        result = options_costs.aggregate_options_total_costs(
            _pnl(50.0),
            {"total_commission_usd": math.nan},
            {"total_slippage_usd": math.inf},
            SPREAD,
        )
        assert result["components_usd"]["commission"] == 0.0
        assert result["components_usd"]["slippage"] == 0.0
        assert result["total_costs_usd"] == 2.0

    def test_bool_cost_and_total_pnl_treated_as_zero(self):
        pnl = {"trade_pnl": [], "total_pnl": True}
        result = options_costs.aggregate_options_total_costs(
            pnl,
            {"total_commission_usd": True},
            SLIPPAGE,
            SPREAD,
        )
        assert result["components_usd"]["commission"] == 0.0
        assert result["gross_profit_usd"] == 0.0
        assert result["total_costs_usd"] == 10.0
        assert result["cost_drag_pct"] is None

    def test_numeric_string_totals_accepted(self):
        result = options_costs.aggregate_options_total_costs(
            {"trade_pnl": [], "total_pnl": "50"},
            {"total_commission_usd": "5.0"},
            {"total_slippage_usd": "8.0"},
            {"total_spread_usd": "2.0"},
        )
        assert result["total_costs_usd"] == 15.0
        assert result["gross_profit_usd"] == 50.0
        assert result["cost_drag_pct"] == 0.3

    def test_negative_component_totals_summed(self):
        result = options_costs.aggregate_options_total_costs(
            _pnl(50.0),
            {"total_commission_usd": -5.0},
            SLIPPAGE,
            SPREAD,
        )
        assert result["components_usd"]["commission"] == -5.0
        assert result["total_costs_usd"] == 5.0
        assert result["cost_drag_pct"] == 0.1

    def test_invalid_total_pnl(self):
        pnl = {"trade_pnl": [], "total_pnl": "bad"}
        result = options_costs.aggregate_options_total_costs(
            pnl, COMMISSIONS, SLIPPAGE, SPREAD
        )
        assert result["gross_profit_usd"] == 0.0
        assert result["cost_drag_pct"] is None

    def test_nan_total_pnl(self):
        pnl = {"trade_pnl": [], "total_pnl": math.nan}
        result = options_costs.aggregate_options_total_costs(
            pnl, COMMISSIONS, SLIPPAGE, SPREAD
        )
        assert result["gross_profit_usd"] == 0.0
        assert result["cost_drag_pct"] is None

    def test_non_dict_regulatory_fees(self):
        result = options_costs.aggregate_options_total_costs(
            _pnl(50.0),
            COMMISSIONS,
            SLIPPAGE,
            SPREAD,
            regulatory_fees="bad",
        )
        assert result["components_usd"]["regulatory_fees"] == 0.0
        assert result["total_costs_usd"] == 15.0

    def test_missing_trade_pnl_key(self):
        result = options_costs.aggregate_options_total_costs(
            {"total_pnl": 50.0}, COMMISSIONS, SLIPPAGE, SPREAD
        )
        assert result["num_closed_trades"] == 0
        assert result["cost_drag_pct"] == 0.3


class TestAggregateOptionsTotalCostsIntegration:
    def test_matches_calculator_outputs(self):
        trades = [
            {"action": "BTO", "contracts": 2, "premium": 3.0},
            {"action": "STC", "contracts": 2, "premium": 4.0},
        ]
        commissions = options_costs.calculate_options_commissions(trades, 0.65)
        slippage = options_costs.calculate_options_slippage(trades)
        spread = options_costs.calculate_options_bid_ask_spread(trades)
        regulatory = options_costs.calculate_options_regulatory_fees(trades)

        pnl = {"trade_pnl": [{"pnl": 200.0}], "total_pnl": 200.0}
        result = options_costs.aggregate_options_total_costs(
            pnl,
            commissions,
            slippage,
            spread,
            regulatory_fees=regulatory,
        )

        expected_total = (
            commissions["total_commission_usd"]
            + slippage["total_slippage_usd"]
            + spread["total_spread_usd"]
            + regulatory["total_regulatory_fees_usd"]
        )
        assert result["total_costs_usd"] == round(expected_total, 4)
        assert result["cost_drag_pct"] == round(expected_total / 200.0, 4)


ACCOUNT_SIZE = 10_000.0


class TestCalculateOptionsAfterCostReturn:
    def test_after_costs_profit_equals_gross_minus_costs(self):
        adj = options_costs.calculate_options_after_cost_return(500.0, 50.0, ACCOUNT_SIZE)
        assert adj["after_costs_profit_usd"] == pytest.approx(450.0)

    def test_after_costs_pct_consistent_with_usd(self):
        adj = options_costs.calculate_options_after_cost_return(500.0, 50.0, ACCOUNT_SIZE)
        expected_pct = adj["after_costs_profit_usd"] / ACCOUNT_SIZE * 100
        assert adj["after_costs_pct"] == pytest.approx(expected_pct, rel=1e-5)

    def test_zero_costs_matches_gross(self):
        adj = options_costs.calculate_options_after_cost_return(500.0, 0.0, ACCOUNT_SIZE)
        assert adj["after_costs_pct"] == pytest.approx(adj["gross_return_pct"])
        assert adj["after_costs_profit_usd"] == pytest.approx(500.0)

    def test_costs_reduce_return_when_gross_positive(self):
        adj = options_costs.calculate_options_after_cost_return(500.0, 50.0, ACCOUNT_SIZE)
        assert adj["after_costs_pct"] < adj["gross_return_pct"]

    def test_negative_gross_subtracts_costs(self):
        adj = options_costs.calculate_options_after_cost_return(-100.0, 15.0, ACCOUNT_SIZE)
        assert adj["after_costs_profit_usd"] == pytest.approx(-115.0)
        assert adj["gross_return_pct"] == pytest.approx(-1.0, rel=1e-5)
        assert adj["after_costs_pct"] == pytest.approx(-1.15, rel=1e-5)

    @pytest.mark.parametrize(
        "bad_size",
        [0, -1.0, math.nan, math.inf, True, "10000", None],
    )
    def test_invalid_account_size_raises(self, bad_size):
        with pytest.raises(ValueError, match="account_size"):
            options_costs.calculate_options_after_cost_return(100.0, 10.0, bad_size)


class TestAggregateOptionsAfterCostReturn:
    def test_omitted_account_size_has_no_return_fields(self):
        result = options_costs.aggregate_options_total_costs(
            _pnl(50.0), COMMISSIONS, SLIPPAGE, SPREAD
        )
        for key in (
            "gross_return_pct",
            "total_costs_pct",
            "after_costs_profit_usd",
            "after_costs_pct",
        ):
            assert key not in result

    def test_with_account_size_includes_after_cost_fields(self):
        result = options_costs.aggregate_options_total_costs(
            _pnl(50.0),
            COMMISSIONS,
            SLIPPAGE,
            SPREAD,
            account_size=ACCOUNT_SIZE,
        )
        assert result["gross_return_pct"] == pytest.approx(0.5, rel=1e-5)
        assert result["total_costs_pct"] == pytest.approx(0.15, rel=1e-5)
        assert result["after_costs_profit_usd"] == pytest.approx(35.0)
        assert result["after_costs_pct"] == pytest.approx(0.35, rel=1e-5)

    @pytest.mark.parametrize("bad_size", [0, True, "10000"])
    def test_invalid_account_size_raises(self, bad_size):
        with pytest.raises(ValueError, match="account_size"):
            options_costs.aggregate_options_total_costs(
                _pnl(50.0),
                COMMISSIONS,
                SLIPPAGE,
                SPREAD,
                account_size=bad_size,
            )
