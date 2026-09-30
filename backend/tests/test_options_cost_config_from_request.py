"""Tests for options_cost_config_from_request (EPIC 9.6)."""

import math

import pytest

import options_costs


class TestOptionsCostConfigFromRequestDefaults:
    def test_none_returns_defaults(self):
        config = options_costs.options_cost_config_from_request(None)
        assert config == options_costs.OptionsCostConfig()

    def test_empty_dict_returns_defaults(self):
        config = options_costs.options_cost_config_from_request({})
        assert config == options_costs.OptionsCostConfig()

    def test_partial_override_leaves_other_fields_default(self):
        config = options_costs.options_cost_config_from_request(
            {"commission_per_contract": 0.65}
        )
        assert config.commission_per_contract == 0.65
        assert config.slippage_pct == options_costs.DEFAULT_OPTIONS_SLIPPAGE_PCT
        assert config.spread_pct == options_costs.DEFAULT_OPTIONS_SPREAD_PCT
        assert config.apply_regulatory_fees is True
        assert (
            config.occ_fee_per_contract
            == options_costs.DEFAULT_OCC_CLEARING_FEE_PER_CONTRACT
        )
        assert config.orf_fee_per_contract == options_costs.DEFAULT_ORF_FEE_PER_CONTRACT
        assert config.sec_fee_rate == options_costs.DEFAULT_SEC_FEE_RATE
        assert (
            config.finra_taf_per_contract
            == options_costs.DEFAULT_FINRA_TAF_PER_CONTRACT
        )

    def test_unknown_keys_ignored(self):
        config = options_costs.options_cost_config_from_request(
            {"commission_per_contract": 1.0, "extra_field": 999}
        )
        assert config.commission_per_contract == 1.0
        assert config.slippage_pct == options_costs.DEFAULT_OPTIONS_SLIPPAGE_PCT


class TestOptionsCostConfigFromRequestOverrides:
    def test_full_override(self):
        raw = {
            "commission_per_contract": 0.5,
            "slippage_pct": 0.02,
            "spread_pct": 0.04,
            "apply_regulatory_fees": False,
            "occ_fee_per_contract": 0.03,
            "orf_fee_per_contract": 0.02,
            "sec_fee_rate": 0.0001,
            "finra_taf_per_contract": 0.003,
        }
        config = options_costs.options_cost_config_from_request(raw)
        assert config.commission_per_contract == 0.5
        assert config.slippage_pct == 0.02
        assert config.spread_pct == 0.04
        assert config.apply_regulatory_fees is False
        assert config.occ_fee_per_contract == 0.03
        assert config.orf_fee_per_contract == 0.02
        assert config.sec_fee_rate == 0.0001
        assert config.finra_taf_per_contract == 0.003

    def test_numeric_string_accepted_like_v1(self):
        config = options_costs.options_cost_config_from_request(
            {"commission_per_contract": "0.65"}
        )
        assert config.commission_per_contract == 0.65

    def test_whitespace_padded_numeric_string_accepted(self):
        config = options_costs.options_cost_config_from_request(
            {"commission_per_contract": " 0.65 "}
        )
        assert config.commission_per_contract == 0.65

    def test_max_caps_at_boundary_accepted(self):
        config = options_costs.options_cost_config_from_request(
            {
                "commission_per_contract": 1000.0,
                "sec_fee_rate": 1.0,
            }
        )
        assert config.commission_per_contract == 1000.0
        assert config.sec_fee_rate == 1.0

    def test_slippage_boundary_zero_and_one(self):
        assert (
            options_costs.options_cost_config_from_request({"slippage_pct": 0}).slippage_pct
            == 0.0
        )
        assert (
            options_costs.options_cost_config_from_request({"slippage_pct": 1}).slippage_pct
            == 1.0
        )


class TestOptionsCostConfigFromRequestRejections:
    @pytest.mark.parametrize(
        "raw",
        [
            {"commission_per_contract": "notanumber"},
            {"commission_per_contract": True},
            {"slippage_pct": object()},
        ],
    )
    def test_non_numeric_rejected(self, raw):
        with pytest.raises(ValueError, match="must be a number"):
            options_costs.options_cost_config_from_request(raw)

    def test_negative_commission_rejected(self):
        with pytest.raises(ValueError, match="non-negative"):
            options_costs.options_cost_config_from_request(
                {"commission_per_contract": -0.01}
            )

    @pytest.mark.parametrize("key", ["slippage_pct", "spread_pct"])
    def test_pct_above_one_rejected(self, key):
        with pytest.raises(ValueError, match="must be <= 1"):
            options_costs.options_cost_config_from_request({key: 1.01})

    def test_apply_regulatory_fees_must_be_bool(self):
        with pytest.raises(ValueError, match="must be a boolean"):
            options_costs.options_cost_config_from_request(
                {"apply_regulatory_fees": "true"}
            )
        with pytest.raises(ValueError, match="must be a boolean"):
            options_costs.options_cost_config_from_request({"apply_regulatory_fees": 1})

    @pytest.mark.parametrize(
        "key",
        [
            "commission_per_contract",
            "occ_fee_per_contract",
            "orf_fee_per_contract",
            "finra_taf_per_contract",
        ],
    )
    def test_per_contract_fee_cap(self, key):
        with pytest.raises(ValueError, match="must be at most"):
            options_costs.options_cost_config_from_request({key: 1000.01})

    def test_sec_fee_rate_cap(self):
        with pytest.raises(ValueError, match="must be at most"):
            options_costs.options_cost_config_from_request({"sec_fee_rate": 1.01})

    def test_nan_and_inf_rejected(self):
        with pytest.raises(ValueError, match="must be a number"):
            options_costs.options_cost_config_from_request(
                {"commission_per_contract": math.nan}
            )
        with pytest.raises(ValueError, match="must be a number"):
            options_costs.options_cost_config_from_request(
                {"commission_per_contract": math.inf}
            )

    def test_huge_int_overflow_rejected(self):
        with pytest.raises(ValueError, match="must be a number"):
            options_costs.options_cost_config_from_request(
                {"commission_per_contract": 10**10000}
            )

    def test_empty_string_form_value_rejected(self):
        with pytest.raises(ValueError, match="must be a number"):
            options_costs.options_cost_config_from_request(
                {"commission_per_contract": ""}
            )

    def test_non_mapping_rejected(self):
        with pytest.raises(ValueError, match="must be an object"):
            options_costs.options_cost_config_from_request([1, 2])  # type: ignore[arg-type]

    def test_empty_list_rejected_not_silent_default(self):
        with pytest.raises(ValueError, match="must be an object"):
            options_costs.options_cost_config_from_request([])  # type: ignore[arg-type]
