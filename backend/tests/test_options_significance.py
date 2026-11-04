"""Tests for options per-position significance via run_significance_tests."""

import options_analyzer
from statistical_tests import VERDICT_DESCRIPTIONS, run_significance_tests

# 30 closed positions: positive mean, enough for min-trade threshold (deterministic verdict).
SAMPLE_TRADE_PNL_VALUES = [10.0] * 18 + [-5.0] * 12


def _trade_pnl(entries: list[float]) -> list[dict]:
    return [{"pnl": pnl} for pnl in entries]


class TestCalculateOptionsSignificance:
    def test_empty_list_returns_none(self):
        assert options_analyzer.calculate_options_significance([]) is None

    def test_all_invalid_returns_none(self):
        raw = [
            {"pnl": "not-a-number"},
            {"pnl": float("nan")},
            {"pnl": True},
            None,
            "not-a-dict",
        ]
        assert options_analyzer.calculate_options_significance(raw) is None

    def test_single_position_insufficient_data(self):
        result = options_analyzer.calculate_options_significance([{"pnl": 10.0}])
        assert result is not None
        assert result["verdict"] == "INSUFFICIENT_DATA"
        assert result["trade_count"] == 1

    def test_thirty_positions_returns_full_result(self):
        trade_pnl = _trade_pnl(SAMPLE_TRADE_PNL_VALUES)
        result = options_analyzer.calculate_options_significance(trade_pnl)
        assert result is not None
        assert set(result.keys()) >= {
            "verdict",
            "ttest",
            "bootstrap_ci",
            "sharpe",
            "winrate",
            "trade_count",
        }
        assert result["trade_count"] == 30
        assert result["verdict"] in VERDICT_DESCRIPTIONS
        assert result["verdict"] == "SIGNIFICANT"

    def test_accepts_numeric_string_pnl(self):
        raw = [{"pnl": "12.5"}, {"pnl": " 3 "}, {"pnl": "  "}, {"pnl": -1.0}]
        result = options_analyzer.calculate_options_significance(raw)
        assert result is not None
        assert result["trade_count"] == 3
        expected = run_significance_tests([12.5, 3.0, -1.0])
        assert result == expected

    def test_skips_invalid_entries_for_trade_count(self):
        raw = [
            {"pnl": 10.0},
            {"pnl": "not-a-number"},
            {"pnl": float("nan")},
            {"pnl": float("inf")},
            {"pnl": True},
            {"pnl": None},
            "not-a-dict",
            {},
            {"pnl": 5.0},
        ]
        result = options_analyzer.calculate_options_significance(raw)
        assert result is not None
        assert result["trade_count"] == 2

    def test_matches_direct_run_on_extracted_values(self):
        trade_pnl = _trade_pnl(SAMPLE_TRADE_PNL_VALUES)
        expected = run_significance_tests(SAMPLE_TRADE_PNL_VALUES)
        assert options_analyzer.calculate_options_significance(trade_pnl) == expected

    def test_does_not_mutate_input(self):
        trade_pnl = [{"pnl": 1.0}, {"pnl": -1.0}]
        snapshot = [dict(e) for e in trade_pnl]
        options_analyzer.calculate_options_significance(trade_pnl)
        assert trade_pnl == snapshot
