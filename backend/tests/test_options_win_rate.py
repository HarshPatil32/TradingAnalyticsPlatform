"""Tests for options win rate with minimum-sample guard."""

import options_analyzer


def _trade_pnl(entries: list[float]) -> list[dict]:
    return [{"pnl": pnl} for pnl in entries]


class TestCalculateOptionsWinRate:
    def test_empty_list(self):
        result = options_analyzer.calculate_options_win_rate([])
        assert result["num_closed_positions"] == 0
        assert result["num_winning_positions"] == 0
        assert result["sufficient_sample"] is False
        assert result["win_rate_pct"] is None
        assert result["confidence_interval_pct"] is None
        assert "No closed positions" in result["message"]

    def test_singular_insufficient_message(self):
        result = options_analyzer.calculate_options_win_rate([{"pnl": 10.0}])
        assert result["num_closed_positions"] == 1
        assert result["message"] == (
            "Only 1 closed position (1 winner). "
            "At least 30 are recommended before a win rate is meaningful."
        )

    def test_below_minimum_sample(self):
        trade_pnl = _trade_pnl([100.0, -50.0, 25.0] * 9 + [10.0, -5.0])  # 29 rows
        assert len(trade_pnl) == 29
        result = options_analyzer.calculate_options_win_rate(trade_pnl)
        assert result["num_closed_positions"] == 29
        assert result["sufficient_sample"] is False
        assert result["win_rate_pct"] is None
        assert result["confidence_interval_pct"] is None
        assert "29 closed positions" in result["message"]
        assert "30" in result["message"]

    def test_exactly_minimum_sample(self):
        trade_pnl = _trade_pnl([10.0] * 18 + [-5.0] * 12)
        result = options_analyzer.calculate_options_win_rate(trade_pnl)
        assert result["num_closed_positions"] == 30
        assert result["num_winning_positions"] == 18
        assert result["sufficient_sample"] is True
        assert result["win_rate_pct"] == 60.0
        assert result["confidence_interval_pct"] == [42.32, 75.41]
        assert "enough for a win rate figure" in result["message"]

    def test_all_wins_at_minimum(self):
        trade_pnl = _trade_pnl([1.0] * 30)
        result = options_analyzer.calculate_options_win_rate(trade_pnl)
        assert result["win_rate_pct"] == 100.0
        assert result["confidence_interval_pct"] == [88.65, 100.0]

    def test_all_losses_at_minimum(self):
        trade_pnl = _trade_pnl([-1.0] * 30)
        result = options_analyzer.calculate_options_win_rate(trade_pnl)
        assert result["win_rate_pct"] == 0.0
        assert result["confidence_interval_pct"] == [0.0, 11.35]

    def test_sufficient_message_singular_winner(self):
        trade_pnl = _trade_pnl([10.0] + [-5.0] * 29)
        result = options_analyzer.calculate_options_win_rate(trade_pnl)
        assert result["sufficient_sample"] is True
        assert result["message"] == (
            "30 closed positions (1 winner), enough for a win rate figure."
        )

    def test_breakeven_counts_as_loss(self):
        trade_pnl = _trade_pnl([0.0] * 30)
        result = options_analyzer.calculate_options_win_rate(trade_pnl)
        assert result["num_winning_positions"] == 0
        assert result["win_rate_pct"] == 0.0

    def test_accepts_string_and_int_pnl(self):
        raw = [{"pnl": "5.0"}, {"pnl": " -3 "}, {"pnl": 2}]
        result = options_analyzer.calculate_options_win_rate(raw)
        assert result["num_closed_positions"] == 3
        assert result["num_winning_positions"] == 2

    def test_skips_invalid_entries(self):
        raw = [
            {"pnl": 10.0},
            {"pnl": "not-a-number"},
            {"pnl": float("nan")},
            {"pnl": float("inf")},
            {"pnl": float("-inf")},
            {"pnl": True},
            {"pnl": None},
            "not-a-dict",
            {},
            {"pnl": 5.0},
        ]
        result = options_analyzer.calculate_options_win_rate(raw)
        assert result["num_closed_positions"] == 2
        assert result["num_winning_positions"] == 2

    def test_does_not_mutate_input(self):
        trade_pnl = [{"pnl": 1.0}, {"pnl": -1.0}]
        snapshot = [dict(e) for e in trade_pnl]
        options_analyzer.calculate_options_win_rate(trade_pnl)
        assert trade_pnl == snapshot
