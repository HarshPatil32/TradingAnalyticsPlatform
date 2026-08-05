"""Tests for normalize_broker_format() in csv_analyzer."""

import csv
import io

from csv_analyzer import normalize_broker_format

ROBINHOOD_HEADER = (
    "Activity Date,Process Date,Settle Date,Instrument,Description,"
    "Trans Code,Quantity,Price,Amount"
)


def _parse_normalized(csv_data: str) -> list[dict]:
    reader = csv.DictReader(io.StringIO(csv_data))
    return list(reader)


class TestNormalizeBrokerFormat:
    def test_buy_row_normalizes_date(self):
        csv_data = (
            f"{ROBINHOOD_HEADER}\n"
            "1/15/2024,1/15/2024,1/17/2024,AAPL,Apple Inc.,BUY,10,$185.00,($1850.00)\n"
        )
        result = _parse_normalized(normalize_broker_format(csv_data))
        assert len(result) == 1
        assert result[0] == {
            "date": "2024-01-15",
            "symbol": "AAPL",
            "action": "BUY",
            "price": "185.00",
            "shares": "10",
        }

    def test_malformed_date_skipped(self):
        csv_data = (
            f"{ROBINHOOD_HEADER}\n"
            "not-a-date,1/15/2024,1/17/2024,AAPL,Apple Inc.,BUY,10,$185.00,($1850.00)\n"
        )
        result = _parse_normalized(normalize_broker_format(csv_data))
        assert result == []
