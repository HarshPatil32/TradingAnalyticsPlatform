"""Tests for calculate_options_regulatory_fees()."""

import pytest

from options_costs import (
    DEFAULT_FINRA_TAF_PER_CONTRACT,
    DEFAULT_OCC_CLEARING_FEE_PER_CONTRACT,
    DEFAULT_ORF_FEE_PER_CONTRACT,
    DEFAULT_SEC_FEE_RATE,
    calculate_options_regulatory_fees,
)


def _expected_rates_used(**overrides):
    base = {
        "occ_fee_per_contract": DEFAULT_OCC_CLEARING_FEE_PER_CONTRACT,
        "orf_fee_per_contract": DEFAULT_ORF_FEE_PER_CONTRACT,
        "sec_fee_rate": DEFAULT_SEC_FEE_RATE,
        "finra_taf_per_contract": DEFAULT_FINRA_TAF_PER_CONTRACT,
    }
    base.update(overrides)
    return base


def test_empty_trades_returns_zeros():
    result = calculate_options_regulatory_fees([])
    assert result == {
        "total_regulatory_fees_usd": 0.0,
        "occ_clearing_usd": 0.0,
        "orf_usd": 0.0,
        "sec_fee_usd": 0.0,
        "finra_taf_usd": 0.0,
        "num_legs": 0,
        "num_sell_legs": 0,
        "rates_used": _expected_rates_used(),
    }


def test_buy_side_legs_no_sec_or_finra():
    legs = [
        {"contracts": 2, "action": "BTO", "premium": 3.50},
        {"contracts": 1, "action": "BTC", "premium": 0.45},
    ]
    result = calculate_options_regulatory_fees(legs)
    assert result["num_legs"] == 2
    assert result["num_sell_legs"] == 0
    assert result["sec_fee_usd"] == 0.0
    assert result["finra_taf_usd"] == 0.0
    assert result["occ_clearing_usd"] == pytest.approx(
        (2 + 1) * DEFAULT_OCC_CLEARING_FEE_PER_CONTRACT
    )
    assert result["orf_usd"] == pytest.approx((2 + 1) * DEFAULT_ORF_FEE_PER_CONTRACT)


def test_sell_side_legs_charge_all_fees():
    legs = [{"contracts": 2, "action": "STC", "premium": 5.0}]
    result = calculate_options_regulatory_fees(legs)
    notional = 5.0 * 2 * 100
    assert result["num_sell_legs"] == 1
    assert result["occ_clearing_usd"] == pytest.approx(2 * DEFAULT_OCC_CLEARING_FEE_PER_CONTRACT)
    assert result["orf_usd"] == pytest.approx(2 * DEFAULT_ORF_FEE_PER_CONTRACT)
    assert result["sec_fee_usd"] == round(DEFAULT_SEC_FEE_RATE * notional, 4)
    assert result["finra_taf_usd"] == round(
        2 * DEFAULT_FINRA_TAF_PER_CONTRACT, 4
    )


def test_mixed_legs_hand_calculated_totals():
    legs = [
        {"contracts": 1, "action": "BTO", "premium": 2.0},
        {"contracts": 3, "action": "STO", "premium": 1.5},
        {"contracts": 2, "action": "stc", "premium": 4.0},
    ]
    result = calculate_options_regulatory_fees(legs)
    total_contracts = 6
    assert result["occ_clearing_usd"] == pytest.approx(
        total_contracts * DEFAULT_OCC_CLEARING_FEE_PER_CONTRACT
    )
    assert result["orf_usd"] == pytest.approx(
        total_contracts * DEFAULT_ORF_FEE_PER_CONTRACT
    )
    sell_notional = 3 * 1.5 * 100 + 2 * 4.0 * 100
    assert result["sec_fee_usd"] == round(DEFAULT_SEC_FEE_RATE * sell_notional, 4)
    finra_raw = 3 * DEFAULT_FINRA_TAF_PER_CONTRACT + 2 * DEFAULT_FINRA_TAF_PER_CONTRACT
    assert result["finra_taf_usd"] == round(finra_raw, 4)
    assert result["num_legs"] == 3
    assert result["num_sell_legs"] == 2
    raw_total = (
        total_contracts * DEFAULT_OCC_CLEARING_FEE_PER_CONTRACT
        + total_contracts * DEFAULT_ORF_FEE_PER_CONTRACT
        + DEFAULT_SEC_FEE_RATE * sell_notional
        + finra_raw
    )
    assert result["total_regulatory_fees_usd"] == round(raw_total, 4)


def test_custom_rate_overrides_in_rates_used():
    result = calculate_options_regulatory_fees(
        [{"contracts": 1, "action": "STC", "premium": 1.0}],
        occ_fee_per_contract=0.05,
        orf_fee_per_contract=0.03,
        sec_fee_rate=0.001,
        finra_taf_per_contract=0.01,
    )
    assert result["rates_used"] == _expected_rates_used(
        occ_fee_per_contract=0.05,
        orf_fee_per_contract=0.03,
        sec_fee_rate=0.001,
        finra_taf_per_contract=0.01,
    )
    assert result["occ_clearing_usd"] == pytest.approx(0.05)
    assert result["orf_usd"] == pytest.approx(0.03)
    assert result["sec_fee_usd"] == pytest.approx(0.001 * 100.0)
    assert result["finra_taf_usd"] == pytest.approx(0.01)


def test_missing_contracts_treated_as_zero():
    legs = [{"action": "BTO"}, {"contracts": 2, "action": "STC", "premium": 2.0}]
    result = calculate_options_regulatory_fees(legs)
    assert result["occ_clearing_usd"] == pytest.approx(2 * DEFAULT_OCC_CLEARING_FEE_PER_CONTRACT)
    assert result["num_sell_legs"] == 1


def test_missing_premium_sec_fee_zero_no_error():
    legs = [{"contracts": 2, "action": "STC"}]
    result = calculate_options_regulatory_fees(legs)
    assert result["sec_fee_usd"] == 0.0
    assert result["finra_taf_usd"] == round(2 * DEFAULT_FINRA_TAF_PER_CONTRACT, 4)


def test_price_fallback_for_sec_notional():
    legs = [{"contracts": 1, "action": "SELL", "price": 3.25}]
    result = calculate_options_regulatory_fees(legs)
    assert result["sec_fee_usd"] == round(DEFAULT_SEC_FEE_RATE * 325.0, 4)


@pytest.mark.parametrize(
    "kwargs,param_name",
    [
        ({"occ_fee_per_contract": -0.01}, "occ_fee_per_contract"),
        ({"orf_fee_per_contract": -0.01}, "orf_fee_per_contract"),
        ({"sec_fee_rate": -0.001}, "sec_fee_rate"),
        ({"finra_taf_per_contract": -0.001}, "finra_taf_per_contract"),
    ],
)
def test_negative_rate_raises(kwargs, param_name):
    with pytest.raises(ValueError, match=f"{param_name} must be >= 0"):
        calculate_options_regulatory_fees([], **kwargs)


def test_non_numeric_contracts_treated_as_zero():
    legs = [{"contracts": "bad", "action": "STO", "premium": 2.0}]
    result = calculate_options_regulatory_fees(legs)
    assert result["num_sell_legs"] == 1
    assert result["total_regulatory_fees_usd"] == 0.0
    assert result["sec_fee_usd"] == 0.0


def test_bool_rate_raises():
    with pytest.raises(ValueError, match="sec_fee_rate must be >= 0"):
        calculate_options_regulatory_fees([], sec_fee_rate=True)
