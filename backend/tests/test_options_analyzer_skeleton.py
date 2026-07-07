"""Smoke tests for the options_analyzer module skeleton."""

import pytest

import options_analyzer


class TestOptionsAnalyzerSkeleton:
    def test_module_imports(self):
        assert options_analyzer.__name__ == "options_analyzer"

    def test_required_options_columns_defined(self):
        assert "date" in options_analyzer.REQUIRED_OPTIONS_COLUMNS
        assert "premium" in options_analyzer.REQUIRED_OPTIONS_COLUMNS

    def test_default_contract_multiplier(self):
        assert options_analyzer.DEFAULT_CONTRACT_MULTIPLIER == 100

    @pytest.mark.parametrize(
        "func_name",
        [
            "sanitize_options_csv",
            "normalize_options_broker_format",
            "detect_options_format",
            "parse_options_detailed",
            "parse_options_summary",
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
            if func_name == "parse_options_detailed":
                func("date,underlying\n")
            elif func_name in (
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
