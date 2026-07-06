"""Tests for parse_summary() in csv_analyzer."""

import pytest

from csv_analyzer import analyze_uploaded_trades, parse_summary

VALID_CSV = (
    "initial_capital,final_balance,num_trades,win_rate,start_date,end_date\n"
    "10000,12000,42,0.6,2024-01-01,2024-12-31\n"
)


class TestParseSummaryHappyPath:
    def test_returns_dict(self):
        assert isinstance(parse_summary(VALID_CSV), dict)

    def test_initial_capital_is_float(self):
        result = parse_summary(VALID_CSV)
        assert isinstance(result["initial_capital"], float)
        assert result["initial_capital"] == 10000.0

    def test_final_balance_is_float(self):
        result = parse_summary(VALID_CSV)
        assert isinstance(result["final_balance"], float)
        assert result["final_balance"] == 12000.0

    def test_num_trades_is_int(self):
        result = parse_summary(VALID_CSV)
        assert isinstance(result["num_trades"], int)
        assert result["num_trades"] == 42

    def test_win_rate_is_float(self):
        result = parse_summary(VALID_CSV)
        assert isinstance(result["win_rate"], float)
        assert result["win_rate"] == 0.6

    def test_start_date_preserved_as_string(self):
        assert parse_summary(VALID_CSV)["start_date"] == "2024-01-01"

    def test_end_date_preserved_as_string(self):
        assert parse_summary(VALID_CSV)["end_date"] == "2024-12-31"

    def test_win_rate_zero_accepted(self):
        csv_data = "initial_capital,final_balance,num_trades,win_rate,start_date,end_date\n10000,5000,10,0.0,2024-01-01,2024-12-31\n"
        assert parse_summary(csv_data)["win_rate"] == 0.0

    def test_win_rate_one_accepted(self):
        csv_data = "initial_capital,final_balance,num_trades,win_rate,start_date,end_date\n10000,20000,10,1.0,2024-01-01,2024-12-31\n"
        assert parse_summary(csv_data)["win_rate"] == 1.0

    def test_same_start_and_end_date_accepted(self):
        csv_data = "initial_capital,final_balance,num_trades,win_rate,start_date,end_date\n10000,12000,1,1.0,2024-06-01,2024-06-01\n"
        result = parse_summary(csv_data)
        assert result["start_date"] == result["end_date"]

    def test_num_trades_as_whole_float_string_accepted(self):
        # "42.0" is an integer value written as float
        csv_data = "initial_capital,final_balance,num_trades,win_rate,start_date,end_date\n10000,12000,42.0,0.6,2024-01-01,2024-12-31\n"
        result = parse_summary(csv_data)
        assert result["num_trades"] == 42
        assert isinstance(result["num_trades"], int)

    def test_extra_columns_ignored(self):
        csv_data = "initial_capital,final_balance,num_trades,win_rate,start_date,end_date,strategy\n10000,12000,42,0.6,2024-01-01,2024-12-31,MACD\n"
        result = parse_summary(csv_data)
        assert "strategy" not in result


class TestParseSummaryColumnHandling:
    def test_mixed_case_headers(self):
        csv_data = "Initial_Capital,Final_Balance,Num_Trades,Win_Rate,Start_Date,End_Date\n10000,12000,42,0.6,2024-01-01,2024-12-31\n"
        assert parse_summary(csv_data)["num_trades"] == 42

    def test_padded_headers(self):
        csv_data = " initial_capital , final_balance , num_trades , win_rate , start_date , end_date \n10000,12000,42,0.6,2024-01-01,2024-12-31\n"
        assert parse_summary(csv_data)["num_trades"] == 42


class TestParseSummaryMissingFields:
    def _drop_col(self, field: str) -> str:
        cols = [
            "initial_capital",
            "final_balance",
            "num_trades",
            "win_rate",
            "start_date",
            "end_date",
        ]
        vals = ["10000", "12000", "42", "0.6", "2024-01-01", "2024-12-31"]
        idx = cols.index(field)
        cols.pop(idx)
        vals.pop(idx)
        return ",".join(cols) + "\n" + ",".join(vals) + "\n"

    @pytest.mark.parametrize(
        "field",
        [
            "initial_capital",
            "final_balance",
            "num_trades",
            "win_rate",
            "start_date",
            "end_date",
        ],
    )
    def test_missing_required_field_raises(self, field):
        with pytest.raises(ValueError, match="missing required fields"):
            parse_summary(self._drop_col(field))

    def test_empty_csv_raises(self):
        with pytest.raises(ValueError):
            parse_summary("")

    def test_header_only_raises(self):
        with pytest.raises(ValueError):
            parse_summary(
                "initial_capital,final_balance,num_trades,win_rate,start_date,end_date\n"
            )


class TestParseSummaryWinRate:
    def _make_csv(self, win_rate: str) -> str:
        return f"initial_capital,final_balance,num_trades,win_rate,start_date,end_date\n10000,12000,42,{win_rate},2024-01-01,2024-12-31\n"

    def test_above_one_raises(self):
        with pytest.raises(ValueError, match="win_rate"):
            parse_summary(self._make_csv("1.01"))

    def test_negative_raises(self):
        with pytest.raises(ValueError, match="win_rate"):
            parse_summary(self._make_csv("-0.01"))

    def test_non_numeric_raises(self):
        with pytest.raises(ValueError, match="win_rate"):
            parse_summary(self._make_csv("abc"))

    def test_percentage_format_raises(self):
        # 60 looks like 60% (not 0.60) and should be rejected
        with pytest.raises(ValueError, match="win_rate"):
            parse_summary(self._make_csv("60"))


class TestParseSummaryDates:
    def _make_csv(self, start: str, end: str) -> str:
        return f"initial_capital,final_balance,num_trades,win_rate,start_date,end_date\n10000,12000,42,0.6,{start},{end}\n"

    def test_slash_format_start_raises(self):
        with pytest.raises(ValueError, match="start_date"):
            parse_summary(self._make_csv("01/01/2024", "2024-12-31"))

    def test_slash_format_end_raises(self):
        with pytest.raises(ValueError, match="end_date"):
            parse_summary(self._make_csv("2024-01-01", "12/31/2024"))

    def test_missing_leading_zero_start_raises(self):
        with pytest.raises(ValueError, match="start_date"):
            parse_summary(self._make_csv("2024-1-1", "2024-12-31"))

    def test_missing_leading_zero_end_raises(self):
        with pytest.raises(ValueError, match="end_date"):
            parse_summary(self._make_csv("2024-01-01", "2024-1-31"))

    def test_start_after_end_raises(self):
        with pytest.raises(ValueError, match="start_date"):
            parse_summary(self._make_csv("2024-12-31", "2024-01-01"))

    def test_invalid_month_raises(self):
        with pytest.raises(ValueError, match="start_date"):
            parse_summary(self._make_csv("2024-13-01", "2024-12-31"))

    def test_error_message_includes_bad_value(self):
        bad = "01/01/2024"
        with pytest.raises(ValueError, match=bad):
            parse_summary(self._make_csv(bad, "2024-12-31"))


class TestParseSummaryNumericFields:
    def _make_csv(
        self, initial: str = "10000", final: str = "12000", trades: str = "42"
    ) -> str:
        return f"initial_capital,final_balance,num_trades,win_rate,start_date,end_date\n{initial},{final},{trades},0.6,2024-01-01,2024-12-31\n"

    def test_zero_initial_capital_raises(self):
        with pytest.raises(ValueError, match="initial_capital"):
            parse_summary(self._make_csv(initial="0"))

    def test_negative_initial_capital_raises(self):
        with pytest.raises(ValueError, match="initial_capital"):
            parse_summary(self._make_csv(initial="-1000"))

    def test_non_numeric_initial_capital_raises(self):
        with pytest.raises(ValueError, match="initial_capital"):
            parse_summary(self._make_csv(initial="abc"))

    def test_zero_final_balance_raises(self):
        with pytest.raises(ValueError, match="final_balance"):
            parse_summary(self._make_csv(final="0"))

    def test_zero_num_trades_raises(self):
        with pytest.raises(ValueError, match="num_trades"):
            parse_summary(self._make_csv(trades="0"))

    def test_fractional_num_trades_raises(self):
        with pytest.raises(ValueError, match="num_trades"):
            parse_summary(self._make_csv(trades="42.5"))

    def test_non_numeric_num_trades_raises(self):
        with pytest.raises(ValueError, match="num_trades"):
            parse_summary(self._make_csv(trades="abc"))


class TestParseSummaryMultipleRows:
    def test_two_data_rows_raises(self):
        csv_data = (
            "initial_capital,final_balance,num_trades,win_rate,start_date,end_date\n"
            "10000,12000,42,0.6,2024-01-01,2024-12-31\n"
            "20000,25000,30,0.7,2023-01-01,2023-12-31\n"
        )
        with pytest.raises(ValueError, match="exactly one data row"):
            parse_summary(csv_data)


class TestParseSummaryIntegration:
    def test_analyze_returns_format_and_summary_keys(self):
        result = analyze_uploaded_trades(VALID_CSV)
        assert result["format"] == "summary"
        assert "summary" in result

    def test_analyze_summary_values_are_typed(self):
        summary = analyze_uploaded_trades(VALID_CSV)["summary"]
        assert isinstance(summary["initial_capital"], float)
        assert isinstance(summary["num_trades"], int)
        assert isinstance(summary["win_rate"], float)

    def test_analyze_invalid_summary_raises_via_entry_point(self):
        bad_csv = "initial_capital,final_balance,num_trades,win_rate,start_date,end_date\n10000,12000,42,1.5,2024-01-01,2024-12-31\n"
        result = analyze_uploaded_trades(bad_csv)
        assert "error" in result
        assert "win_rate" in result["error"]


class TestParseSummaryWhitespaceCells:
    def test_whitespace_padded_data_cells_parsed(self):
        csv_data = (
            "initial_capital,final_balance,num_trades,win_rate,start_date,end_date\n"
            "  10000  ,  12000  ,  42  ,  0.6  ,  2024-01-01  ,  2024-12-31  \n"
        )
        result = parse_summary(csv_data)
        assert result["initial_capital"] == 10000.0
        assert result["num_trades"] == 42
        assert result["win_rate"] == 0.6
        assert result["start_date"] == "2024-01-01"
        assert result["end_date"] == "2024-12-31"
