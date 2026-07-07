"""Import and integration tests for overfitting_detector and statistical_tests."""

import sys

# Import resolution


class TestImports:
    def test_statistical_tests_importable(self):
        import statistical_tests  # noqa: F401

    def test_overfitting_detector_importable(self):
        import overfitting_detector  # noqa: F401

    def test_sharpe_significance_exported(self):
        from statistical_tests import sharpe_significance

        assert callable(sharpe_significance)

    def test_winrate_binomial_test_exported(self):
        from statistical_tests import winrate_binomial_test

        assert callable(winrate_binomial_test)

    def test_overfitting_detector_uses_sharpe_significance(self):
        """Verify overfitting_detector binds sharpe_significance from statistical_tests."""
        import overfitting_detector
        from statistical_tests import sharpe_significance

        assert overfitting_detector.sharpe_significance is sharpe_significance

    def test_overfitting_detector_uses_winrate_binomial_test(self):
        """Verify overfitting_detector binds winrate_binomial_test from statistical_tests."""
        import overfitting_detector
        from statistical_tests import winrate_binomial_test

        assert overfitting_detector.winrate_binomial_test is winrate_binomial_test


# No circular imports


class TestNoCircularImport:
    def test_statistical_tests_does_not_import_overfitting_detector(self):
        """statistical_tests must not import overfitting_detector (circular guard)."""
        import statistical_tests

        assert (
            "overfitting_detector" not in sys.modules
            or "statistical_tests" in sys.modules
        )  # statistical_tests loaded first cleanly

        # Check the module's own namespace for any reference to overfitting_detector
        source_file = statistical_tests.__file__
        with open(source_file, "r") as f:
            source = f.read()
        assert (
            "overfitting_detector" not in source
        ), "statistical_tests.py must not import overfitting_detector"

    def test_fresh_import_order_statistical_tests_first(self):
        """Importing statistical_tests before overfitting_detector must succeed."""
        # Remove both from sys.modules to simulate a fresh interpreter
        for mod in ("statistical_tests", "overfitting_detector"):
            sys.modules.pop(mod, None)

        import overfitting_detector  # noqa: F401
        import statistical_tests  # noqa: F401

    def test_fresh_import_order_overfitting_detector_first(self):
        """Importing overfitting_detector first must pull in statistical_tests cleanly."""
        for mod in ("statistical_tests", "overfitting_detector"):
            sys.modules.pop(mod, None)

        import overfitting_detector  # noqa: F401

        assert "statistical_tests" in sys.modules


# Functional integration — overfitting_detector calls statistical_tests helpers

TYPICAL_PNL = [0.5, -0.2, 1.1, 0.3, -0.4, 0.8, 0.6, -0.1, 0.9, 0.2] * 5  # 50 trades


class TestIntegration:
    def test_score_sharpe_uses_sharpe_significance(self):
        """score_sharpe must produce a dict that embeds a sharpe_test sub-result."""
        from overfitting_detector import score_sharpe

        result = score_sharpe(TYPICAL_PNL)
        assert "score" in result
        assert "sharpe_test" in result
        assert isinstance(result["sharpe_test"], dict)

    def test_score_win_rate_uses_winrate_binomial_test(self):
        """score_win_rate must embed the full binomial_test sub-result."""
        from overfitting_detector import score_win_rate

        result = score_win_rate(TYPICAL_PNL)
        assert "score" in result
        assert "binomial_test" in result
        assert isinstance(result["binomial_test"], dict)

    def test_detect_overfitting_returns_complete_dict(self):
        from overfitting_detector import detect_overfitting

        result = detect_overfitting(pnl_list=TYPICAL_PNL)
        assert "overfitting_score" in result
        assert "factor_scores" in result
        assert isinstance(result["overfitting_score"], (int, float))

    def test_sharpe_significance_result_surfaced_in_factor_scores(self):
        """sharpe_test from statistical_tests must be nested inside factor_scores.sharpe."""
        from overfitting_detector import detect_overfitting

        result = detect_overfitting(pnl_list=TYPICAL_PNL)
        sharpe_factor = result["factor_scores"]["sharpe"]
        assert "sharpe_test" in sharpe_factor
        assert "significant" in sharpe_factor["sharpe_test"]

    def test_winrate_significance_result_surfaced_in_factor_scores(self):
        """binomial_test from statistical_tests must be nested inside factor_scores.win_rate."""
        from overfitting_detector import detect_overfitting

        result = detect_overfitting(pnl_list=TYPICAL_PNL)
        win_rate_factor = result["factor_scores"]["win_rate"]
        assert "binomial_test" in win_rate_factor
        assert "significant" in win_rate_factor["binomial_test"]
