"""Tests for calculate_options_slippage()."""

import pytest

from options_costs import (
    DEFAULT_OPTIONS_SLIPPAGE_PCT,
    calculate_options_slippage,
)


def test_empty_trades_returns_zeros():
    result = calculate_options_slippage([])
    assert result == {
        "total_slippage_usd": 0.0,
        "per_leg_avg_usd": 0.0,
        "num_legs": 0,
        "slippage_pct_used": DEFAULT_OPTIONS_SLIPPAGE_PCT,
        "per_leg_breakdown": [],
    }


def test_zero_slippage_pct_returns_zeros():
    legs = [{"contracts": 2, "action": "BTO", "premium": 3.50}]
    result = calculate_options_slippage(legs, slippage_pct=0.0)
    assert result["total_slippage_usd"] == 0.0
    assert result["per_leg_breakdown"][0]["slippage_usd"] == 0.0
    assert result["slippage_pct_used"] == 0.0


def test_single_leg_known_premium_and_contracts():
    # 0.03 × 2.5 × 3 × 100 = 22.5
    legs = [{"contracts": 3, "action": "BTO", "premium": 2.5}]
    result = calculate_options_slippage(legs, slippage_pct=0.03)
    assert result["total_slippage_usd"] == pytest.approx(22.5)
    assert result["num_legs"] == 1
    assert result["per_leg_avg_usd"] == pytest.approx(22.5)
    entry = result["per_leg_breakdown"][0]
    assert entry["notional_usd"] == pytest.approx(750.0)
    assert entry["slippage_usd"] == pytest.approx(22.5)


def test_multi_leg_total_equals_sum_of_breakdown():
    legs = [
        {"contracts": 1, "action": "BTO", "premium": 2.0},
        {"contracts": 2, "action": "STC", "premium": 4.0},
    ]
    rate = 0.03
    result = calculate_options_slippage(legs, slippage_pct=rate)
    breakdown_total = sum(e["slippage_usd"] for e in result["per_leg_breakdown"])
    assert result["total_slippage_usd"] == breakdown_total
    # leg1: 0.03 × 2.0 × 1 × 100 = 6.0; leg2: 0.03 × 4.0 × 2 × 100 = 24.0
    assert result["total_slippage_usd"] == pytest.approx(30.0)
    assert result["num_legs"] == 2


def test_missing_premium_leg_contributes_zero_slippage():
    legs = [{"contracts": 2, "action": "BTO"}, {"contracts": 1, "action": "STC", "premium": 5.0}]
    result = calculate_options_slippage(legs, slippage_pct=0.03)
    assert result["per_leg_breakdown"][0]["slippage_usd"] == 0.0
    assert result["per_leg_breakdown"][1]["slippage_usd"] == pytest.approx(15.0)


def test_price_fallback_used_when_premium_absent():
    legs = [{"contracts": 1, "action": "BTO", "price": 3.25}]
    result = calculate_options_slippage(legs, slippage_pct=0.03)
    assert result["per_leg_breakdown"][0]["premium"] == pytest.approx(3.25)
    assert result["total_slippage_usd"] == pytest.approx(0.03 * 325.0)


def test_empty_string_premium_falls_back_to_price():
    legs = [{"contracts": 1, "action": "BTO", "premium": "", "price": 3.25}]
    result = calculate_options_slippage(legs, slippage_pct=0.03)
    assert result["per_leg_breakdown"][0]["premium"] == pytest.approx(3.25)
    assert result["total_slippage_usd"] == pytest.approx(0.03 * 325.0)


def test_empty_string_premium_without_price_contributes_zero_slippage():
    legs = [{"contracts": 2, "action": "BTO", "premium": ""}]
    result = calculate_options_slippage(legs, slippage_pct=0.03)
    assert result["total_slippage_usd"] == 0.0
    assert result["per_leg_breakdown"][0]["slippage_usd"] == 0.0


def test_negative_premium_uses_abs_notional():
    legs = [{"contracts": 2, "action": "BTO", "premium": -2.5}]
    result = calculate_options_slippage(legs, slippage_pct=0.03)
    assert result["per_leg_breakdown"][0]["notional_usd"] == pytest.approx(500.0)
    assert result["total_slippage_usd"] == pytest.approx(15.0)


def test_non_numeric_premium_contributes_zero_slippage():
    legs = [{"contracts": 2, "action": "BTO", "premium": "bad"}]
    result = calculate_options_slippage(legs, slippage_pct=0.03)
    assert result["total_slippage_usd"] == 0.0


def test_non_numeric_contracts_contributes_zero_slippage():
    legs = [{"contracts": "bad", "action": "BTO", "premium": 2.0}]
    result = calculate_options_slippage(legs, slippage_pct=0.03)
    assert result["total_slippage_usd"] == 0.0


def test_negative_slippage_pct_raises():
    with pytest.raises(ValueError, match="slippage_pct must be >= 0"):
        calculate_options_slippage([], slippage_pct=-0.01)


def test_slippage_pct_above_1_raises():
    with pytest.raises(ValueError, match="slippage_pct must be <= 1"):
        calculate_options_slippage([], slippage_pct=1.5)


def test_slippage_pct_at_max_boundary_is_valid():
    result = calculate_options_slippage([], slippage_pct=1.0)
    assert result["slippage_pct_used"] == 1.0


def test_bool_slippage_pct_raises():
    with pytest.raises(ValueError, match="slippage_pct must be >= 0"):
        calculate_options_slippage([], slippage_pct=True)


def test_breakdown_has_required_keys():
    legs = [{"contracts": 1, "action": "bto", "premium": 1.0}]
    result = calculate_options_slippage(legs)
    entry = result["per_leg_breakdown"][0]
    assert set(entry.keys()) == {
        "action",
        "contracts",
        "premium",
        "notional_usd",
        "slippage_usd",
    }
    assert entry["action"] == "BTO"


def test_per_leg_avg_correct():
    legs = [
        {"contracts": 1, "action": "BTO", "premium": 10.0},
        {"contracts": 1, "action": "STC", "premium": 10.0},
    ]
    result = calculate_options_slippage(legs, slippage_pct=0.01)
    assert result["per_leg_avg_usd"] == pytest.approx(
        result["total_slippage_usd"] / 2
    )


def test_slippage_pct_used_echoed_in_result():
    result = calculate_options_slippage([], slippage_pct=0.05)
    assert result["slippage_pct_used"] == 0.05


def test_zero_contracts_contributes_zero_slippage():
    legs = [{"contracts": 0, "action": "BTO", "premium": 5.0}]
    result = calculate_options_slippage(legs, slippage_pct=0.03)
    assert result["total_slippage_usd"] == 0.0


def test_custom_slippage_pct_override():
    legs = [{"contracts": 1, "action": "BTO", "premium": 100.0}]
    result = calculate_options_slippage(legs, slippage_pct=0.02)
    assert result["slippage_pct_used"] == 0.02
    assert result["total_slippage_usd"] == pytest.approx(0.02 * 100 * 100)
