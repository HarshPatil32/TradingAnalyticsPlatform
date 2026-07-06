"""Smoke tests for the options_costs module skeleton."""

import pytest

import options_costs


class TestOptionsCostsSkeleton:
    def test_module_imports(self):
        assert options_costs.__name__ == "options_costs"

    def test_default_cost_constants(self):
        assert options_costs.DEFAULT_OPTIONS_COMMISSION_PER_CONTRACT == 0.00
        assert options_costs.DEFAULT_OPTIONS_SLIPPAGE_PCT == 0.03
        assert options_costs.DEFAULT_OPTIONS_SPREAD_PCT == 0.05
        assert options_costs.DEFAULT_OCC_CLEARING_FEE_PER_CONTRACT == 0.02
        assert options_costs.DEFAULT_ORF_FEE_PER_CONTRACT == 0.01
        assert options_costs.DEFAULT_SEC_FEE_RATE == 0.0000278
        assert options_costs.DEFAULT_FINRA_TAF_PER_CONTRACT == 0.00279

    def test_options_cost_config_defaults(self):
        config = options_costs.OptionsCostConfig()
        assert (
            config.commission_per_contract
            == options_costs.DEFAULT_OPTIONS_COMMISSION_PER_CONTRACT
        )
        assert config.slippage_pct == options_costs.DEFAULT_OPTIONS_SLIPPAGE_PCT
        assert config.spread_pct == options_costs.DEFAULT_OPTIONS_SPREAD_PCT
        assert config.apply_regulatory_fees is True

    @pytest.mark.parametrize(
        "func_name",
        [
            "calculate_options_commissions",
            "calculate_options_regulatory_fees",
            "calculate_options_slippage",
            "calculate_options_bid_ask_spread",
            "calculate_options_real_costs",
        ],
    )
    def test_public_stubs_raise_not_implemented(self, func_name):
        func = getattr(options_costs, func_name)
        with pytest.raises(NotImplementedError):
            if func_name == "calculate_options_real_costs":
                func([], 10_000.0)
            else:
                func([])
