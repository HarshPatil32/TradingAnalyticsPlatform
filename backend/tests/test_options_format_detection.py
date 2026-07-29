"""Tests for detect_options_format() in options_analyzer."""

import pytest

from options_analyzer import detect_options_format, sanitize_options_csv

DETAILED_HEADER = (
    "date,underlying,option_type,action,strike,expiration,contracts,premium"
)
SUMMARY_HEADER = "initial_capital,final_balance,num_trades,win_rate,start_date,end_date"


class TestDetectOptionsFormat:
    def test_exact_detailed_columns(self):
        csv_data = (
            f"{DETAILED_HEADER}\n" "2024-01-15,AAPL,CALL,BTO,190.00,2024-02-16,2,3.50\n"
        )
        assert detect_options_format(csv_data) == "detailed"

    def test_exact_summary_columns(self):
        csv_data = f"{SUMMARY_HEADER}\n10000,12000,42,0.6,2024-01-01,2024-12-31\n"
        assert detect_options_format(csv_data) == "summary"

    def test_detailed_with_extra_columns(self):
        csv_data = (
            f"{DETAILED_HEADER},multiplier,fees\n"
            "2024-01-15,AAPL,CALL,BTO,190.00,2024-02-16,2,3.50,100,1.30\n"
        )
        assert detect_options_format(csv_data) == "detailed"

    def test_summary_with_extra_columns(self):
        csv_data = (
            f"{SUMMARY_HEADER},strategy\n"
            "10000,12000,42,0.6,2024-01-01,2024-12-31,iron_condor\n"
        )
        assert detect_options_format(csv_data) == "summary"

    def test_mixed_case_headers_detailed(self):
        csv_data = (
            "Date,Underlying,Option_Type,Action,Strike,Expiration,Contracts,Premium\n"
            "2024-01-15,AAPL,CALL,BTO,190.00,2024-02-16,2,3.50\n"
        )
        assert detect_options_format(csv_data) == "detailed"

    def test_mixed_case_headers_summary(self):
        csv_data = (
            "Initial_Capital,Final_Balance,Num_Trades,Win_Rate,Start_Date,End_Date\n"
            "10000,12000,42,0.6,2024-01-01,2024-12-31\n"
        )
        assert detect_options_format(csv_data) == "summary"

    def test_whitespace_padded_headers_detailed(self):
        csv_data = (
            " date , underlying , option_type , action , strike , expiration , contracts , premium \n"
            "2024-01-15,AAPL,CALL,BTO,190.00,2024-02-16,2,3.50\n"
        )
        assert detect_options_format(csv_data) == "detailed"

    def test_whitespace_padded_headers_summary(self):
        csv_data = (
            " initial_capital , final_balance , num_trades , win_rate , start_date , end_date \n"
            "10000,12000,42,0.6,2024-01-01,2024-12-31\n"
        )
        assert detect_options_format(csv_data) == "summary"

    def test_unknown_columns_raises(self):
        csv_data = "foo,bar,baz\n1,2,3\n"
        with pytest.raises(ValueError, match="missing these columns"):
            detect_options_format(csv_data)

    def test_empty_string_raises(self):
        with pytest.raises(ValueError, match="empty or has no header row"):
            detect_options_format("")

    def test_header_only_no_data_rows_still_detects(self):
        assert detect_options_format(DETAILED_HEADER) == "detailed"
        assert detect_options_format(SUMMARY_HEADER) == "summary"

    def test_partial_detailed_columns_raises(self):
        csv_data = "date,underlying,option_type\n2024-01-15,AAPL,CALL\n"
        with pytest.raises(ValueError, match="missing these columns"):
            detect_options_format(csv_data)

    def test_whitespace_only_raises(self):
        with pytest.raises(ValueError, match="empty or has no header row"):
            detect_options_format("   \n\n  ")

    def test_blank_lines_only_raises(self):
        with pytest.raises(ValueError, match="empty or has no header row"):
            detect_options_format("\n\n\n")

    def test_partial_summary_columns_raises(self):
        csv_data = "initial_capital,final_balance\n10000,12000\n"
        with pytest.raises(ValueError, match="missing these columns"):
            detect_options_format(csv_data)

    def test_semicolon_delimited_after_sanitize(self):
        raw = (
            "date;underlying;option_type;action;strike;expiration;contracts;premium\n"
            "2024-01-15;AAPL;CALL;BTO;190.00;2024-02-16;2;3.50\n"
        )
        clean = sanitize_options_csv(raw)
        assert detect_options_format(clean) == "detailed"

    def test_detailed_takes_priority_over_summary_when_both_match(self):
        combined = f"{DETAILED_HEADER},{SUMMARY_HEADER}\n"
        combined += (
            "2024-01-15,AAPL,CALL,BTO,190.00,2024-02-16,2,3.50,"
            "10000,12000,42,0.6,2024-01-01,2024-12-31\n"
        )
        assert detect_options_format(combined) == "detailed"
