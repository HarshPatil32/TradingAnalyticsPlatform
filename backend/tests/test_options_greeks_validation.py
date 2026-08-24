"""Tests for input validation in options_greeks."""

import pytest

import options_greeks

INVALID_POSITIVE = [0, -1, float("nan"), float("inf"), float("-inf"), "abc"]
INVALID_NON_NEGATIVE = [-1, float("nan"), float("inf"), float("-inf"), "abc"]

FUNCTIONS_WITH_VOLATILITY = [
    "black_scholes_price",
    "calculate_delta",
    "calculate_gamma",
    "calculate_theta",
    "calculate_vega",
    "calculate_rho",
    "calculate_greeks",
]


def _call_with_option_type(func_name: str, **overrides):
    func = getattr(options_greeks, func_name)
    defaults = {
        "option_type": "call",
        "spot": 100.0,
        "strike": 100.0,
        "time_to_expiry": 1.0,
        "volatility": 0.2,
    }
    defaults.update(overrides)
    if func_name == "calculate_implied_volatility":
        defaults.setdefault("market_price", 5.0)
        return func(
            defaults["option_type"],
            defaults["market_price"],
            defaults["spot"],
            defaults["strike"],
            defaults["time_to_expiry"],
        )
    if func_name in ("calculate_gamma", "calculate_vega"):
        return func(
            defaults["spot"],
            defaults["strike"],
            defaults["time_to_expiry"],
            defaults["volatility"],
        )
    return func(
        defaults["option_type"],
        defaults["spot"],
        defaults["strike"],
        defaults["time_to_expiry"],
        defaults["volatility"],
    )


class TestValidatePositive:
    @pytest.mark.parametrize("func_name", FUNCTIONS_WITH_VOLATILITY)
    @pytest.mark.parametrize(
        "field", ["spot", "strike", "time_to_expiry", "volatility"]
    )
    @pytest.mark.parametrize("value", INVALID_POSITIVE)
    def test_invalid_positive_inputs_raise(self, func_name, field, value):
        with pytest.raises(ValueError, match=f"{field} must be positive"):
            _call_with_option_type(func_name, **{field: value})

    @pytest.mark.parametrize("field", ["spot", "strike", "time_to_expiry"])
    @pytest.mark.parametrize("value", INVALID_POSITIVE)
    def test_implied_volatility_invalid_positive_inputs_raise(self, field, value):
        with pytest.raises(ValueError, match=f"{field} must be positive"):
            _call_with_option_type("calculate_implied_volatility", **{field: value})


class TestValidateNonNegative:
    @pytest.mark.parametrize("value", INVALID_NON_NEGATIVE)
    def test_invalid_market_price_raises(self, value):
        with pytest.raises(ValueError, match="market_price must be non-negative"):
            _call_with_option_type("calculate_implied_volatility", market_price=value)

    def test_zero_market_price_reaches_not_implemented(self):
        with pytest.raises(NotImplementedError):
            _call_with_option_type("calculate_implied_volatility", market_price=0.0)


class TestValidInputsReachNotImplemented:
    @pytest.mark.parametrize("func_name", FUNCTIONS_WITH_VOLATILITY)
    def test_valid_inputs_reach_not_implemented(self, func_name):
        with pytest.raises(NotImplementedError):
            _call_with_option_type(func_name)

    def test_implied_volatility_valid_inputs_reach_not_implemented(self):
        with pytest.raises(NotImplementedError):
            _call_with_option_type("calculate_implied_volatility")
