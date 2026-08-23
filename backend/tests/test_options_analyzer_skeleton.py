"""Smoke tests for the options_analyzer module skeleton."""

import pytest

import options_analyzer
from csv_analyzer import REQUIRED_SUMMARY_KEYS


class TestOptionsAnalyzerSkeleton:
    def test_module_imports(self):
        assert options_analyzer.__name__ == "options_analyzer"

    def test_required_options_columns_defined(self):
        assert options_analyzer.REQUIRED_OPTIONS_COLUMNS == frozenset(
            {
                "date",
                "underlying",
                "option_type",
                "action",
                "strike",
                "expiration",
                "contracts",
                "premium",
            }
        )

    def test_optional_options_columns_defined(self):
        assert options_analyzer.OPTIONAL_OPTIONS_COLUMNS == frozenset(
            {"multiplier", "fees"}
        )

    def test_required_and_optional_columns_disjoint(self):
        assert options_analyzer.REQUIRED_OPTIONS_COLUMNS.isdisjoint(
            options_analyzer.OPTIONAL_OPTIONS_COLUMNS
        )

    def test_required_options_summary_columns_defined(self):
        assert options_analyzer.REQUIRED_OPTIONS_SUMMARY_COLUMNS == frozenset(
            {
                "initial_capital",
                "final_balance",
                "num_trades",
                "win_rate",
                "start_date",
                "end_date",
            }
        )

    def test_options_summary_columns_match_stock_summary_keys(self):
        assert (
            options_analyzer.REQUIRED_OPTIONS_SUMMARY_COLUMNS == REQUIRED_SUMMARY_KEYS
        )

    def test_summary_columns_disjoint_from_required(self):
        assert options_analyzer.REQUIRED_OPTIONS_SUMMARY_COLUMNS.isdisjoint(
            options_analyzer.REQUIRED_OPTIONS_COLUMNS
        )

    def test_valid_option_types(self):
        assert options_analyzer.VALID_OPTION_TYPES == frozenset({"CALL", "PUT"})

    def test_valid_option_actions(self):
        assert options_analyzer.VALID_OPTION_ACTIONS == frozenset(
            {"BTO", "STO", "BTC", "STC", "OEXP", "OASGN"}
        )

    def test_schema_constants_are_frozensets(self):
        for name in (
            "REQUIRED_OPTIONS_COLUMNS",
            "OPTIONAL_OPTIONS_COLUMNS",
            "REQUIRED_OPTIONS_SUMMARY_COLUMNS",
            "VALID_OPTION_TYPES",
            "VALID_OPTION_ACTIONS",
        ):
            assert isinstance(getattr(options_analyzer, name), frozenset)

    def test_default_contract_multiplier(self):
        assert options_analyzer.DEFAULT_CONTRACT_MULTIPLIER == 100
        assert isinstance(options_analyzer.DEFAULT_CONTRACT_MULTIPLIER, int)

    def test_free_tier_options_row_limit(self):
        assert options_analyzer.FREE_TIER_OPTIONS_ROW_LIMIT == 100
        assert isinstance(options_analyzer.FREE_TIER_OPTIONS_ROW_LIMIT, int)

    @pytest.mark.parametrize(
        "func_name",
        [
            "validate_options",
            "calculate_options_pnl",
            "check_theta_decay_risk",
            "check_expired_worthless_pattern",
            "check_naked_selling_habit",
            "analyze_uploaded_options",
        ],
    )
    def test_public_stubs_raise_not_implemented(self, func_name):
        func = getattr(options_analyzer, func_name)
        with pytest.raises(NotImplementedError):
            if func_name in (
                "validate_options",
                "check_theta_decay_risk",
                "check_naked_selling_habit",
            ):
                func([])
            elif func_name == "check_expired_worthless_pattern":
                func({})
            elif func_name == "calculate_options_pnl":
                func([])
            else:
                func("")
