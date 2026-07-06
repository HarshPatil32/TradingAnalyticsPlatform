"""Smoke tests for the options_greeks module skeleton."""

import pytest

import options_greeks


class TestOptionsGreeksSkeleton:
    def test_module_imports(self):
        assert options_greeks.__name__ == "options_greeks"

    def test_default_pricing_constants(self):
        assert options_greeks.DEFAULT_RISK_FREE_RATE == 0.05
        assert options_greeks.DEFAULT_DIVIDEND_YIELD == 0.00
        assert options_greeks.DEFAULT_IMPLIED_VOL_GUESS == 0.30
        assert options_greeks.DEFAULT_IMPLIED_VOL_MAX_ITERATIONS == 100
        assert options_greeks.DEFAULT_IMPLIED_VOL_TOLERANCE == 1e-6
        assert options_greeks.MIN_IMPLIED_VOL == 0.001
        assert options_greeks.MAX_IMPLIED_VOL == 5.0
        assert options_greeks.TRADING_DAYS_PER_YEAR == 252

    def test_greeks_config_defaults(self):
        config = options_greeks.GreeksConfig()
        assert config.risk_free_rate == options_greeks.DEFAULT_RISK_FREE_RATE
        assert config.dividend_yield == options_greeks.DEFAULT_DIVIDEND_YIELD
        assert config.implied_vol_guess == options_greeks.DEFAULT_IMPLIED_VOL_GUESS
        assert (
            config.implied_vol_max_iterations
            == options_greeks.DEFAULT_IMPLIED_VOL_MAX_ITERATIONS
        )
        assert (
            config.implied_vol_tolerance == options_greeks.DEFAULT_IMPLIED_VOL_TOLERANCE
        )

    @pytest.mark.parametrize(
        "func_name",
        [
            "black_scholes_price",
            "calculate_implied_volatility",
            "calculate_delta",
            "calculate_gamma",
            "calculate_theta",
            "calculate_vega",
            "calculate_rho",
            "calculate_greeks",
        ],
    )
    def test_public_stubs_raise_not_implemented(self, func_name):
        func = getattr(options_greeks, func_name)
        with pytest.raises(NotImplementedError):
            if func_name == "calculate_implied_volatility":
                func("call", 5.0, 100.0, 100.0, 1.0)
            elif func_name in ("calculate_gamma", "calculate_vega"):
                func(100.0, 100.0, 1.0, 0.2)
            else:
                func("call", 100.0, 100.0, 1.0, 0.2)
