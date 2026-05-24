"""Smoke tests for the three analysis modules with minimum viable input."""
import pytest

from statistical_tests import run_significance_tests
from overfitting_detector import detect_overfitting
from transaction_costs import calculate_real_costs
from csv_analyzer import check_disposition_effect
# Fixtures

ONE_TRADE_PNL = [5.0]
ZERO_TRADES_PNL = []
NEGATIVE_PNL = [-3.0, -2.5, -1.8]

ZERO_TRADES_LIST = []

ONE_TRADE_DETAILED = [
    {"date": "2024-01-15", "symbol": "AAPL", "action": "BUY",  "price": 185.50, "shares": 10},
    {"date": "2024-02-20", "symbol": "AAPL", "action": "SELL", "price": 195.20, "shares": 10},
]

NEGATIVE_TRADE_DETAILED = [
    {"date": "2024-01-15", "symbol": "AAPL", "action": "BUY",  "price": 200.0, "shares": 10},
    {"date": "2024-02-20", "symbol": "AAPL", "action": "SELL", "price": 185.0, "shares": 10},
]

# statistical_tests — run_significance_tests

class TestRunSignificanceTestsEdgeCases:
    def test_zero_trades_returns_dict(self):
        result = run_significance_tests(ZERO_TRADES_PNL)
        assert isinstance(result, dict)

    def test_zero_trades_has_verdict(self):
        result = run_significance_tests(ZERO_TRADES_PNL)
        assert "verdict" in result

    def test_zero_trades_verdict_is_insufficient(self):
        result = run_significance_tests(ZERO_TRADES_PNL)
        assert result["verdict"] == "INSUFFICIENT_DATA"

    def test_one_trade_returns_dict(self):
        result = run_significance_tests(ONE_TRADE_PNL)
        assert isinstance(result, dict)

    def test_one_trade_has_verdict(self):
        result = run_significance_tests(ONE_TRADE_PNL)
        assert "verdict" in result

    def test_one_trade_verdict_is_insufficient(self):
        result = run_significance_tests(ONE_TRADE_PNL)
        assert result["verdict"] == "INSUFFICIENT_DATA"

    def test_negative_returns_returns_dict(self):
        result = run_significance_tests(NEGATIVE_PNL)
        assert isinstance(result, dict)

    def test_negative_returns_has_verdict(self):
        result = run_significance_tests(NEGATIVE_PNL)
        assert "verdict" in result

    def test_negative_returns_warns_about_negative_mean(self):
        result = run_significance_tests(NEGATIVE_PNL)
        assert any("negative" in w.lower() for w in result.get("warnings", []))


# overfitting_detector — detect_overfitting

class TestDetectOverfittingEdgeCases:
    def test_zero_trades_returns_dict(self):
        result = detect_overfitting(ZERO_TRADES_PNL)
        assert isinstance(result, dict)

    def test_zero_trades_has_score(self):
        result = detect_overfitting(ZERO_TRADES_PNL)
        assert "overfitting_score" in result

    def test_zero_trades_score_is_zero(self):
        result = detect_overfitting(ZERO_TRADES_PNL)
        assert result["overfitting_score"] == 0.0

    def test_one_trade_returns_dict(self):
        result = detect_overfitting(ONE_TRADE_PNL)
        assert isinstance(result, dict)

    def test_one_trade_has_score(self):
        result = detect_overfitting(ONE_TRADE_PNL)
        assert "overfitting_score" in result

    def test_one_trade_score_in_valid_range(self):
        result = detect_overfitting(ONE_TRADE_PNL)
        assert 0.0 <= result["overfitting_score"] <= 100.0

    def test_negative_returns_returns_dict(self):
        result = detect_overfitting(NEGATIVE_PNL)
        assert isinstance(result, dict)

    def test_negative_returns_has_score(self):
        result = detect_overfitting(NEGATIVE_PNL)
        assert "overfitting_score" in result

    def test_negative_returns_score_in_valid_range(self):
        result = detect_overfitting(NEGATIVE_PNL)
        assert 0.0 <= result["overfitting_score"] <= 100.0

    def test_negative_returns_has_risk_tier(self):
        result = detect_overfitting(NEGATIVE_PNL)
        assert "risk_tier" in result
        assert isinstance(result["risk_tier"], str)


# transaction_costs — calculate_real_costs

class TestCalculateRealCostsEdgeCases:
    def test_zero_trades_returns_dict(self):
        result = calculate_real_costs(ZERO_TRADES_LIST, account_size=10_000)
        assert isinstance(result, dict)

    def test_zero_trades_has_cost_summary(self):
        result = calculate_real_costs(ZERO_TRADES_LIST, account_size=10_000)
        assert "cost_summary" in result

    def test_zero_trades_total_costs_are_zero(self):
        result = calculate_real_costs(ZERO_TRADES_LIST, account_size=10_000)
        assert result["cost_summary"]["total_trading_costs_usd"] == 0.0

    def test_one_trade_returns_dict(self):
        result = calculate_real_costs(ONE_TRADE_DETAILED, account_size=10_000)
        assert isinstance(result, dict)

    def test_one_trade_has_adjusted_returns(self):
        result = calculate_real_costs(ONE_TRADE_DETAILED, account_size=10_000)
        assert "adjusted_returns" in result

    def test_one_trade_commissions_are_zero_by_default(self):
        # Default is $0 commission (commission-free brokers)
        result = calculate_real_costs(ONE_TRADE_DETAILED, account_size=10_000)
        assert result["commissions"]["total_commission_usd"] == 0.0

    def test_negative_returns_returns_dict(self):
        result = calculate_real_costs(NEGATIVE_TRADE_DETAILED, account_size=10_000)
        assert isinstance(result, dict)

    def test_negative_returns_has_adjusted_returns(self):
        result = calculate_real_costs(NEGATIVE_TRADE_DETAILED, account_size=10_000)
        assert "adjusted_returns" in result

    def test_negative_returns_gross_profit_is_negative(self):
        result = calculate_real_costs(NEGATIVE_TRADE_DETAILED, account_size=10_000)
        assert result["adjusted_returns"]["gross_profit_usd"] < 0


# Helper to build minimal pnl_data for disposition effect tests
def _make_pnl_data(avg_winner_days, avg_loser_days, num_winners=3, num_losers=3):
    trade_pnl = (
        [{"pnl": 1.0, "buy_date": "2024-01-01", "sell_date": "2024-01-01"}] * num_winners
        + [{"pnl": -1.0, "buy_date": "2024-01-01", "sell_date": "2024-01-01"}] * num_losers
    )
    return {
        "trade_pnl": trade_pnl,
        "avg_holding_days_winners": avg_winner_days,
        "avg_holding_days_losers": avg_loser_days,
    }


class TestCheckDispositionEffect:
    def test_returns_none_when_no_winner_avg(self):
        pnl = _make_pnl_data(None, 20.0, num_winners=5, num_losers=5)
        assert check_disposition_effect(pnl) is None

    def test_returns_none_when_no_loser_avg(self):
        pnl = _make_pnl_data(10.0, None, num_winners=5, num_losers=5)
        assert check_disposition_effect(pnl) is None

    def test_returns_none_when_winner_avg_is_zero(self):
        pnl = _make_pnl_data(0, 20.0, num_winners=5, num_losers=5)
        assert check_disposition_effect(pnl) is None

    def test_returns_none_when_below_threshold(self):
        # losers held 10 days, winners 8 days — ratio 1.25, below the 1.5 threshold
        pnl = _make_pnl_data(8.0, 10.0, num_winners=5, num_losers=5)
        assert check_disposition_effect(pnl) is None

    def test_returns_none_when_losers_held_same_as_winners(self):
        pnl = _make_pnl_data(10.0, 10.0, num_winners=5, num_losers=5)
        assert check_disposition_effect(pnl) is None

    def test_returns_none_when_too_few_winners(self):
        # only 2 winners — below the 5-trade minimum
        pnl = _make_pnl_data(5.0, 20.0, num_winners=2, num_losers=5)
        assert check_disposition_effect(pnl) is None

    def test_returns_none_when_too_few_losers(self):
        pnl = _make_pnl_data(5.0, 20.0, num_winners=5, num_losers=2)
        assert check_disposition_effect(pnl) is None

    def test_returns_warning_when_triggered(self):
        # losers held 20 days, winners 5 days — ratio 4.0, well above 1.5
        pnl = _make_pnl_data(5.0, 20.0, num_winners=5, num_losers=5)
        result = check_disposition_effect(pnl)
        assert result is not None

    def test_warning_has_correct_type(self):
        pnl = _make_pnl_data(5.0, 20.0, num_winners=5, num_losers=5)
        result = check_disposition_effect(pnl)
        assert result["type"] == "disposition_effect"

    def test_warning_level_is_warning(self):
        pnl = _make_pnl_data(5.0, 20.0, num_winners=5, num_losers=5)
        result = check_disposition_effect(pnl)
        assert result["level"] == "warning"

    def test_warning_message_mentions_days(self):
        pnl = _make_pnl_data(5.0, 20.0, num_winners=5, num_losers=5)
        result = check_disposition_effect(pnl)
        assert "20" in result["message"] and "5" in result["message"]

    def test_warning_message_mentions_disposition_effect(self):
        pnl = _make_pnl_data(5.0, 20.0, num_winners=5, num_losers=5)
        result = check_disposition_effect(pnl)
        assert "disposition effect" in result["message"].lower()

    def test_returns_none_when_winners_held_longer(self):
        # winners held longer than losers — no bias to flag
        pnl = _make_pnl_data(30.0, 5.0, num_winners=5, num_losers=5)
        assert check_disposition_effect(pnl) is None

    def test_triggers_at_exactly_threshold(self):
        # ratio exactly 1.5 — should trigger
        pnl = _make_pnl_data(10.0, 15.0, num_winners=5, num_losers=5)
        assert check_disposition_effect(pnl) is not None

    def test_zero_winner_duration_does_not_warn(self):
        pnl = _make_pnl_data(0, 100.0, num_winners=5, num_losers=5)
        assert check_disposition_effect(pnl) is None
