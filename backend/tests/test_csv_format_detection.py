"""Tests for detect_format() in csv_analyzer."""

import pytest

from csv_analyzer import detect_format, sanitize_csv

DETAILED_HEADER = "date,symbol,action,price,shares"
SUMMARY_HEADER = "initial_capital,final_balance,num_trades,win_rate,start_date,end_date"


class TestDetectFormat:
    def test_exact_detailed_columns(self):
        csv_data = f"{DETAILED_HEADER}\n2024-01-15,AAPL,BUY,185.50,10\n"
        assert detect_format(csv_data) == "detailed"

    def test_exact_summary_columns(self):
        csv_data = f"{SUMMARY_HEADER}\n10000,12000,42,0.6,2024-01-01,2024-12-31\n"
        assert detect_format(csv_data) == "summary"

    def test_detailed_with_extra_columns(self):
        csv_data = "date,symbol,action,price,shares,notes,broker\n2024-01-15,AAPL,BUY,185.50,10,entry,TD\n"
        assert detect_format(csv_data) == "detailed"

    def test_summary_with_extra_columns(self):
        csv_data = "initial_capital,final_balance,num_trades,win_rate,start_date,end_date,strategy\n10000,12000,42,0.6,2024-01-01,2024-12-31,MACD\n"
        assert detect_format(csv_data) == "summary"

    def test_mixed_case_headers_detailed(self):
        csv_data = "Date,Symbol,Action,Price,Shares\n2024-01-15,AAPL,BUY,185.50,10\n"
        assert detect_format(csv_data) == "detailed"

    def test_mixed_case_headers_summary(self):
        csv_data = "Initial_Capital,Final_Balance,Num_Trades,Win_Rate,Start_Date,End_Date\n10000,12000,42,0.6,2024-01-01,2024-12-31\n"
        assert detect_format(csv_data) == "summary"

    def test_whitespace_padded_headers(self):
        csv_data = (
            " date , symbol , action , price , shares \n2024-01-15,AAPL,BUY,185.50,10\n"
        )
        assert detect_format(csv_data) == "detailed"

    def test_unknown_columns_raises(self):
        csv_data = "foo,bar,baz\n1,2,3\n"
        with pytest.raises(ValueError, match="missing these columns"):
            detect_format(csv_data)

    def test_empty_string_raises(self):
        with pytest.raises(ValueError, match="empty or has no header row"):
            detect_format("")

    def test_header_only_no_data_rows_still_detects(self):
        # format detection reads the header only; absence of data rows is fine
        assert detect_format(DETAILED_HEADER) == "detailed"
        assert detect_format(SUMMARY_HEADER) == "summary"

    def test_partial_detailed_columns_raises(self):
        # Only 3 of 5 required detailed columns present
        csv_data = "date,symbol,action\n2024-01-15,AAPL,BUY\n"
        with pytest.raises(ValueError, match="missing these columns"):
            detect_format(csv_data)

    def test_whitespace_only_raises(self):
        with pytest.raises(ValueError, match="empty or has no header row"):
            detect_format("   \n\n  ")

    def test_blank_lines_only_raises(self):
        with pytest.raises(ValueError, match="empty or has no header row"):
            detect_format("\n\n\n")

    def test_partial_summary_columns_raises(self):
        csv_data = "initial_capital,final_balance\n10000,12000\n"
        with pytest.raises(ValueError, match="missing these columns"):
            detect_format(csv_data)

    def test_semicolon_delimited_after_sanitize(self):
        # Confirm detect_format works on data already normalised by sanitize_csv
        raw = "date;symbol;action;price;shares\n2024-01-15;AAPL;BUY;185.50;10\n"
        clean = sanitize_csv(raw)
        assert detect_format(clean) == "detailed"

    def test_detailed_takes_priority_over_summary_when_both_match(self):
        # A file with all columns of both formats should resolve to 'detailed'
        combined = f"{DETAILED_HEADER},{SUMMARY_HEADER}\n"
        combined += (
            "2024-01-15,AAPL,BUY,185.50,10,10000,12000,42,0.6,2024-01-01,2024-12-31\n"
        )
        assert detect_format(combined) == "detailed"
