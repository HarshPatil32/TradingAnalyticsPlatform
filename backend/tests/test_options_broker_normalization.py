"""Tests for normalize_options_broker_format() in options_analyzer."""

import csv
import io

from options_analyzer import normalize_options_broker_format

ROBINHOOD_HEADER = (
    "Activity Date,Process Date,Settle Date,Instrument,Description,"
    "Trans Code,Quantity,Price,Amount"
)


def _parse_normalized(csv_data: str) -> list[dict]:
    reader = csv.DictReader(io.StringIO(csv_data))
    return list(reader)


class TestNormalizeOptionsBrokerFormat:
    def test_bto_stc_pair_normalizes(self):
        csv_data = (
            f"{ROBINHOOD_HEADER}\n"
            "1/15/2024,1/15/2024,1/17/2024,,AAPL 1/19/2024 Call $185.00,"
            "BTO,2,$4.30,($860.00)\n"
            "1/22/2024,1/22/2024,1/24/2024,,AAPL 1/19/2024 Call $185.00,"
            "STC,2,$7.10,$1420.00\n"
        )
        result = _parse_normalized(normalize_options_broker_format(csv_data))
        assert len(result) == 2
        assert result[0] == {
            "date": "2024-01-15",
            "underlying": "AAPL",
            "option_type": "CALL",
            "action": "BTO",
            "strike": "185.00",
            "expiration": "2024-01-19",
            "contracts": "2",
            "premium": "4.30",
        }
        assert result[1] == {
            "date": "2024-01-22",
            "underlying": "AAPL",
            "option_type": "CALL",
            "action": "STC",
            "strike": "185.00",
            "expiration": "2024-01-19",
            "contracts": "2",
            "premium": "7.10",
        }

    def test_oexp_row_normalizes_with_zero_premium(self):
        csv_data = (
            f"{ROBINHOOD_HEADER}\n"
            "1/19/2024,1/19/2024,1/22/2024,,AAPL 1/19/2024 Call $185.00,"
            "OEXP,2,,$0.00\n"
        )
        result = _parse_normalized(normalize_options_broker_format(csv_data))
        assert len(result) == 1
        assert result[0]["action"] == "OEXP"
        assert float(result[0]["premium"]) == 0.0

    def test_oexp_with_explicit_zero_price_normalizes(self):
        csv_data = (
            f"{ROBINHOOD_HEADER}\n"
            "1/19/2024,1/19/2024,1/22/2024,,AAPL 1/19/2024 Call $185.00,"
            "OEXP,2,$0.00,$0.00\n"
        )
        result = _parse_normalized(normalize_options_broker_format(csv_data))
        assert len(result) == 1
        assert result[0]["action"] == "OEXP"
        assert float(result[0]["premium"]) == 0.0

    def test_oasgn_row_normalizes_with_zero_premium(self):
        csv_data = (
            f"{ROBINHOOD_HEADER}\n"
            "3/15/2024,3/15/2024,3/18/2024,,AAPL 3/15/2024 Put $180.00,"
            "OASGN,1,,$0.00\n"
        )
        result = _parse_normalized(normalize_options_broker_format(csv_data))
        assert len(result) == 1
        assert result[0]["action"] == "OASGN"
        assert result[0]["option_type"] == "PUT"
        assert float(result[0]["premium"]) == 0.0

    def test_mixed_stock_and_options_rows_filters_stock(self):
        csv_data = (
            f"{ROBINHOOD_HEADER}\n"
            "1/15/2024,1/15/2024,1/17/2024,AAPL,Apple Inc.,BUY,10,$185.00,($1850.00)\n"
            "1/15/2024,1/15/2024,1/17/2024,,AAPL 1/19/2024 Call $185.00,"
            "BTO,2,$4.30,($860.00)\n"
            "1/20/2024,1/20/2024,1/22/2024,AAPL,Apple Inc.,SELL,10,$190.00,$1900.00\n"
        )
        result = _parse_normalized(normalize_options_broker_format(csv_data))
        assert len(result) == 1
        assert result[0]["action"] == "BTO"

    def test_unknown_trans_code_filtered_out(self):
        csv_data = (
            f"{ROBINHOOD_HEADER}\n"
            "1/15/2024,1/15/2024,1/17/2024,AAPL,Apple Inc.,CDIV,0,$0.00,$5.00\n"
            "1/15/2024,1/15/2024,1/17/2024,,AAPL 1/19/2024 Call $185.00,"
            "BTO,2,$4.30,($860.00)\n"
        )
        result = _parse_normalized(normalize_options_broker_format(csv_data))
        assert len(result) == 1
        assert result[0]["action"] == "BTO"

    def test_transfer_row_filtered_out(self):
        csv_data = (
            f"{ROBINHOOD_HEADER}\n"
            "1/10/2024,1/10/2024,1/10/2024,,ACH Deposit,ACH,1,$0.00,$500.00\n"
            "1/15/2024,1/15/2024,1/17/2024,,AAPL 1/19/2024 Call $185.00,"
            "BTO,2,$4.30,($860.00)\n"
        )
        result = _parse_normalized(normalize_options_broker_format(csv_data))
        assert len(result) == 1
        assert result[0]["action"] == "BTO"

    def test_cash_management_row_filtered_out(self):
        csv_data = (
            f"{ROBINHOOD_HEADER}\n"
            "1/1/2024,1/1/2024,1/1/2024,,Interest Payment,INT,0,$0.00,$1.25\n"
            "1/15/2024,1/15/2024,1/17/2024,,AAPL 1/19/2024 Call $185.00,"
            "BTO,2,$4.30,($860.00)\n"
        )
        result = _parse_normalized(normalize_options_broker_format(csv_data))
        assert len(result) == 1
        assert result[0]["action"] == "BTO"

    def test_all_non_option_rows_returns_empty(self):
        csv_data = (
            f"{ROBINHOOD_HEADER}\n"
            "1/15/2024,1/15/2024,1/17/2024,AAPL,Apple Inc.,BUY,10,$185.00,($1850.00)\n"
            "1/15/2024,1/15/2024,1/17/2024,AAPL,Apple Inc.,CDIV,0,$0.00,$5.00\n"
            "1/10/2024,1/10/2024,1/10/2024,,ACH Deposit,ACH,1,$0.00,$500.00\n"
        )
        result = _parse_normalized(normalize_options_broker_format(csv_data))
        assert result == []

    def test_non_options_trans_code_filtered_despite_valid_description(self):
        csv_data = (
            f"{ROBINHOOD_HEADER}\n"
            "1/15/2024,1/15/2024,1/17/2024,,AAPL 1/19/2024 Call $185.00,"
            "ACH,2,$4.30,($860.00)\n"
        )
        result = _parse_normalized(normalize_options_broker_format(csv_data))
        assert result == []

    def test_malformed_description_skipped(self):
        csv_data = (
            f"{ROBINHOOD_HEADER}\n"
            "1/15/2024,1/15/2024,1/17/2024,,Not an option description,BTO,2,$4.30,($860.00)\n"
        )
        result = _parse_normalized(normalize_options_broker_format(csv_data))
        assert result == []

    def test_malformed_date_skipped(self):
        csv_data = (
            f"{ROBINHOOD_HEADER}\n"
            "not-a-date,1/15/2024,1/17/2024,,AAPL 1/19/2024 Call $185.00,"
            "BTO,2,$4.30,($860.00)\n"
        )
        result = _parse_normalized(normalize_options_broker_format(csv_data))
        assert result == []

    def test_header_only_returns_canonical_header(self):
        result = normalize_options_broker_format(ROBINHOOD_HEADER)
        lines = result.strip().split("\n")
        assert lines == [
            "date,underlying,option_type,action,strike,expiration,contracts,premium"
        ]

    def test_non_robinhood_csv_unchanged(self):
        csv_data = "date,underlying,option_type,action\n2024-01-15,AAPL,CALL,BTO\n"
        assert normalize_options_broker_format(csv_data) == csv_data

    def test_empty_csv_unchanged(self):
        assert normalize_options_broker_format("") == ""

    def test_btc_row_normalizes(self):
        csv_data = (
            f"{ROBINHOOD_HEADER}\n"
            "3/1/2024,3/1/2024,3/5/2024,,AAPL 3/15/2024 Put $180.00,"
            "BTC,3,$0.45,($135.00)\n"
        )
        result = _parse_normalized(normalize_options_broker_format(csv_data))
        assert len(result) == 1
        assert result[0]["action"] == "BTC"
        assert result[0]["option_type"] == "PUT"
        assert result[0]["contracts"] == "3"
        assert result[0]["premium"] == "0.45"

    def test_blank_quantity_passes_through(self):
        csv_data = (
            f"{ROBINHOOD_HEADER}\n"
            "1/15/2024,1/15/2024,1/17/2024,,AAPL 1/19/2024 Call $185.00,"
            "BTO,,$4.30,($860.00)\n"
        )
        result = _parse_normalized(normalize_options_broker_format(csv_data))
        assert len(result) == 1
        assert result[0]["contracts"] == ""

    def test_put_option_type_normalized(self):
        csv_data = (
            f"{ROBINHOOD_HEADER}\n"
            "2/5/2024,2/5/2024,2/7/2024,,AAPL 3/15/2024 Put $180.00,"
            "STO,3,$2.10,$630.00\n"
        )
        result = _parse_normalized(normalize_options_broker_format(csv_data))
        assert len(result) == 1
        assert result[0]["option_type"] == "PUT"
        assert result[0]["action"] == "STO"

    def test_strike_with_comma_parsed(self):
        csv_data = (
            f"{ROBINHOOD_HEADER}\n"
            '1/15/2024,1/15/2024,1/17/2024,,"BRK.B 1/19/2024 Call $1,850.00",'
            "BTO,1,$10.00,($1000.00)\n"
        )
        result = _parse_normalized(normalize_options_broker_format(csv_data))
        assert len(result) == 1
        assert result[0]["underlying"] == "BRK.B"
        assert result[0]["strike"] == "1850.00"
