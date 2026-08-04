"""Tests for _detect_options_broker_format() in options_analyzer."""

from options_analyzer import _detect_options_broker_format

ROBINHOOD_HEADER = (
    "Activity Date,Process Date,Settle Date,Instrument,Description,"
    "Trans Code,Quantity,Price,Amount"
)


class TestDetectOptionsBrokerFormat:
    def test_detects_robinhood_by_exact_headers(self):
        csv_data = (
            f"{ROBINHOOD_HEADER}\n"
            "1/15/2024,1/15/2024,1/17/2024,AAPL,AAPL 1/19/2024 Call $185.00,"
            "BTO,2,$4.30,($860.00)\n"
        )
        assert _detect_options_broker_format(csv_data) == "robinhood"

    def test_detects_robinhood_with_extra_columns(self):
        csv_data = (
            f"{ROBINHOOD_HEADER},Notes\n"
            "1/15/2024,1/15/2024,1/17/2024,AAPL,AAPL 1/19/2024 Call $185.00,"
            "BTO,2,$4.30,($860.00),extra\n"
        )
        assert _detect_options_broker_format(csv_data) == "robinhood"

    def test_detects_robinhood_stock_only_export(self):
        csv_data = (
            f"{ROBINHOOD_HEADER}\n"
            "1/15/2024,1/15/2024,1/17/2024,AAPL,Apple Inc.,BUY,10,$185.00,($1850.00)\n"
            "1/20/2024,1/20/2024,1/22/2024,AAPL,Apple Inc.,SELL,10,$190.00,$1900.00\n"
        )
        assert _detect_options_broker_format(csv_data) == "robinhood"

    def test_detects_robinhood_options_export(self):
        csv_data = (
            f"{ROBINHOOD_HEADER}\n"
            "1/15/2024,1/15/2024,1/17/2024,,AAPL 1/19/2024 Call $185.00,"
            "BTO,2,$4.30,($860.00)\n"
            "1/22/2024,1/22/2024,1/24/2024,,AAPL 1/19/2024 Call $185.00,"
            "STC,2,$7.10,$1420.00\n"
        )
        assert _detect_options_broker_format(csv_data) == "robinhood"

    def test_mixed_case_and_whitespace_headers(self):
        csv_data = (
            " Activity Date , Process Date , Settle Date , Instrument , Description , "
            "Trans Code , Quantity , Price , Amount \n"
            "1/15/2024,1/15/2024,1/17/2024,AAPL,AAPL 1/19/2024 Call $185.00,"
            "BTO,2,$4.30,($860.00)\n"
        )
        assert _detect_options_broker_format(csv_data) == "robinhood"

    def test_unknown_format_returns_none(self):
        csv_data = "date,underlying,option_type,action\n2024-01-15,AAPL,CALL,BTO\n"
        assert _detect_options_broker_format(csv_data) is None

    def test_empty_csv_returns_none(self):
        assert _detect_options_broker_format("") is None

    def test_header_only_no_data_rows_still_detects(self):
        assert _detect_options_broker_format(ROBINHOOD_HEADER) == "robinhood"

    def test_partial_robinhood_headers_returns_none(self):
        csv_data = (
            "Activity Date,Process Date,Instrument,Description,Trans Code\n"
            "1/15/2024,1/15/2024,AAPL,AAPL 1/19/2024 Call $185.00,BTO\n"
        )
        assert _detect_options_broker_format(csv_data) is None
