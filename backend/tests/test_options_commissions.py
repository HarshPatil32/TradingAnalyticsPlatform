"""Tests for calculate_options_commissions()."""

import pytest

from options_costs import (
    DEFAULT_OPTIONS_COMMISSION_PER_CONTRACT,
    calculate_options_commissions,
)


def test_zero_commission_default_empty_trades():
    result = calculate_options_commissions([])
    assert result == {
        "total_commission_usd": 0.0,
        "per_leg_avg_usd": 0.0,
        "num_legs": 0,
        "commission_rate": DEFAULT_OPTIONS_COMMISSION_PER_CONTRACT,
    }


def test_zero_rate_returns_zero():
    legs = [
        {"contracts": 2, "action": "BTO"},
        {"contracts": 2, "action": "STC"},
    ]
    result = calculate_options_commissions(legs, commission_per_contract=0.0)
    assert result["total_commission_usd"] == 0.0
    assert result["per_leg_avg_usd"] == 0.0
    assert result["num_legs"] == 2
    assert result["commission_rate"] == 0.0


def test_flat_rate_single_leg():
    legs = [{"contracts": 2, "action": "BTO"}]
    result = calculate_options_commissions(legs, commission_per_contract=0.65)
    assert result["total_commission_usd"] == pytest.approx(1.3)
    assert result["per_leg_avg_usd"] == pytest.approx(1.3)
    assert result["num_legs"] == 1
    assert result["commission_rate"] == 0.65


def test_flat_rate_multi_leg():
    legs = [
        {"contracts": 1, "action": "BTO"},
        {"contracts": 3, "action": "STC"},
        {"contracts": 2, "action": "BTO"},
    ]
    rate = 0.65
    result = calculate_options_commissions(legs, commission_per_contract=rate)
    # (1 + 3 + 2) * 0.65 = 3.9
    assert result["total_commission_usd"] == pytest.approx(3.9)
    assert result["per_leg_avg_usd"] == pytest.approx(3.9 / 3)
    assert result["num_legs"] == 3
    assert result["commission_rate"] == rate


def test_negative_rate_raises():
    with pytest.raises(ValueError, match="commission_per_contract must be >= 0"):
        calculate_options_commissions([], commission_per_contract=-0.01)


def test_missing_contracts_field_treated_as_zero():
    legs = [{"action": "BTO"}, {"contracts": 2, "action": "STC"}]
    result = calculate_options_commissions(legs, commission_per_contract=1.0)
    assert result["total_commission_usd"] == 2.0
    assert result["num_legs"] == 2


def test_non_numeric_contracts_treated_as_zero():
    legs = [{"contracts": "bad", "action": "BTO"}]
    result = calculate_options_commissions(legs, commission_per_contract=1.0)
    assert result["total_commission_usd"] == 0.0
    assert result["num_legs"] == 1


def test_bool_commission_rate_raises():
    with pytest.raises(ValueError, match="commission_per_contract must be >= 0"):
        calculate_options_commissions([], commission_per_contract=True)


def test_zero_contracts_on_leg_contributes_no_commission():
    legs = [
        {"contracts": 0, "action": "BTO"},
        {"contracts": 2, "action": "STC"},
    ]
    result = calculate_options_commissions(legs, commission_per_contract=0.65)
    assert result["total_commission_usd"] == pytest.approx(1.3)
    assert result["num_legs"] == 2
