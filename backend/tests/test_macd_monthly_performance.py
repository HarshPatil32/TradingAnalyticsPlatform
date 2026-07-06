"""Tests for monthly_performance data structure from GET /MACD-strategy."""

import re
from datetime import datetime
from unittest.mock import patch

from MACD_trading import generate_monthly_performance

INITIAL_BALANCE = 100_000
FINAL_BALANCE = 115_000
START = datetime(2023, 1, 1)
END = datetime(2024, 1, 1)  # 12 months
EXPECTED_MONTHS = 12
SYMBOLS = ["AAPL"]

MOCK_PATCH = "MACD_trading.backtest_strategy_MACD"


@patch(MOCK_PATCH, return_value=("result", FINAL_BALANCE))
class TestMonthlyPerformanceStructure:
    """Confirm the shape of monthly_performance matches what the frontend chart expects."""

    def test_returns_list(self, _):
        result = generate_monthly_performance(SYMBOLS, START, END, INITIAL_BALANCE)
        assert isinstance(result, list)

    def test_length_is_months_plus_one(self, _):
        # months + 1 because "Start" entry is prepended
        result = generate_monthly_performance(SYMBOLS, START, END, INITIAL_BALANCE)
        assert len(result) == EXPECTED_MONTHS + 1

    def test_all_entries_have_required_keys(self, _):
        result = generate_monthly_performance(SYMBOLS, START, END, INITIAL_BALANCE)
        for entry in result:
            assert "month" in entry
            assert "balance" in entry
            assert "date" in entry

    def test_first_entry_is_start(self, _):
        result = generate_monthly_performance(SYMBOLS, START, END, INITIAL_BALANCE)
        first = result[0]
        assert first["month"] == "Start"
        assert first["balance"] == INITIAL_BALANCE
        assert first["date"] == "2023-01"

    def test_last_entry_uses_actual_final_balance(self, _):
        result = generate_monthly_performance(SYMBOLS, START, END, INITIAL_BALANCE)
        last = result[-1]
        assert last["balance"] == FINAL_BALANCE
        assert last["month"] == f"Month {EXPECTED_MONTHS}"

    def test_month_labels_follow_naming_convention(self, _):
        # Frontend uses entry.month as the x-axis label verbatim
        result = generate_monthly_performance(SYMBOLS, START, END, INITIAL_BALANCE)
        assert result[0]["month"] == "Start"
        for i, entry in enumerate(result[1:], start=1):
            assert entry["month"] == f"Month {i}"

    def test_date_format_is_yyyy_mm(self, _):
        result = generate_monthly_performance(SYMBOLS, START, END, INITIAL_BALANCE)
        pattern = re.compile(r"^\d{4}-\d{2}$")
        for entry in result:
            assert pattern.match(
                entry["date"]
            ), f"date '{entry['date']}' does not match YYYY-MM"

    def test_balance_values_are_numeric(self, _):
        result = generate_monthly_performance(SYMBOLS, START, END, INITIAL_BALANCE)
        for entry in result:
            assert isinstance(entry["balance"], (int, float))

    def test_balance_values_are_positive(self, _):
        result = generate_monthly_performance(SYMBOLS, START, END, INITIAL_BALANCE)
        for entry in result:
            assert entry["balance"] > 0

    def test_balance_supports_frontend_rounding(self, _):
        # Frontend does Math.round(entry.balance) before passing to Recharts
        result = generate_monthly_performance(SYMBOLS, START, END, INITIAL_BALANCE)
        for entry in result:
            rounded = round(entry["balance"])
            assert isinstance(rounded, int)

    def test_intermediate_balances_are_between_start_and_end(self, _):
        # With positive growth the intermediate values should lie between the two endpoints
        result = generate_monthly_performance(SYMBOLS, START, END, INITIAL_BALANCE)
        lo, hi = min(INITIAL_BALANCE, FINAL_BALANCE), max(
            INITIAL_BALANCE, FINAL_BALANCE
        )
        for entry in result[1:-1]:
            assert lo <= entry["balance"] <= hi

    def test_works_with_multiple_symbols(self, _):
        result = generate_monthly_performance(
            ["AAPL", "MSFT"], START, END, INITIAL_BALANCE
        )
        assert len(result) == EXPECTED_MONTHS + 1
        assert result[0]["balance"] == INITIAL_BALANCE
        assert result[-1]["balance"] == FINAL_BALANCE


@patch(MOCK_PATCH, return_value=("result", FINAL_BALANCE))
class TestMonthlyPerformanceEdgeCases:

    def test_sub_one_month_range_clamps_to_one_month(self, _):
        # start and end in the same month -> months=0, clamped to 1
        start = datetime(2023, 3, 1)
        end = datetime(2023, 3, 20)
        result = generate_monthly_performance(SYMBOLS, start, end, INITIAL_BALANCE)
        assert len(result) == 2  # "Start" + "Month 1"
        assert result[0]["month"] == "Start"
        assert result[1]["month"] == "Month 1"

    def test_negative_return_handled_gracefully(self, mock_backtest):
        # Strategy can lose money; structure must still be valid
        mock_backtest.return_value = ("result", 85_000)
        result = generate_monthly_performance(SYMBOLS, START, END, INITIAL_BALANCE)
        assert len(result) == EXPECTED_MONTHS + 1
        assert result[-1]["balance"] == 85_000
        for entry in result:
            assert "month" in entry and "balance" in entry and "date" in entry
