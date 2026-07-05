from csv_analyzer import FreeTierLimitExceeded
"""Tests for parse_detailed() in csv_analyzer."""
import pytest

from csv_analyzer import parse_detailed, FREE_TIER_TRADE_LIMIT, analyze_uploaded_trades


VALID_CSV = "date,symbol,action,price,shares\n2024-01-15,AAPL,BUY,185.50,10\n2024-02-20,AAPL,SELL,195.20,10\n"


class TestParseDetailedHappyPath:
    def test_returns_list(self):
        result = parse_detailed(VALID_CSV)
        assert isinstance(result, list)

    def test_correct_row_count(self):
        result = parse_detailed(VALID_CSV)
        assert len(result) == 2

    def test_date_preserved_as_string(self):
        result = parse_detailed(VALID_CSV)
        assert result[0]["date"] == "2024-01-15"

    def test_symbol_uppercased(self):
        result = parse_detailed(VALID_CSV)
        assert result[0]["symbol"] == "AAPL"

    def test_action_value(self):
        result = parse_detailed(VALID_CSV)
        assert result[0]["action"] == "BUY"
        assert result[1]["action"] == "SELL"

    def test_price_is_float(self):
        result = parse_detailed(VALID_CSV)
        assert isinstance(result[0]["price"], float)
        assert result[0]["price"] == 185.50

    def test_shares_is_float(self):
        result = parse_detailed(VALID_CSV)
        assert isinstance(result[0]["shares"], float)
        assert result[0]["shares"] == 10.0

    def test_header_only_returns_empty_list(self):
        result = parse_detailed("date,symbol,action,price,shares\n")
        assert result == []

    def test_fractional_shares_accepted(self):
        csv_data = "date,symbol,action,price,shares\n2024-01-15,TSLA,BUY,250.00,0.5\n"
        result = parse_detailed(csv_data)
        assert result[0]["shares"] == 0.5


class TestParseDetailedColumnHandling:
    def test_mixed_case_headers(self):
        csv_data = "Date,Symbol,Action,Price,Shares\n2024-01-15,AAPL,BUY,185.50,10\n"
        result = parse_detailed(csv_data)
        assert len(result) == 1

    def test_padded_headers(self):
        csv_data = " date , symbol , action , price , shares \n2024-01-15,AAPL,BUY,185.50,10\n"
        result = parse_detailed(csv_data)
        assert len(result) == 1

    def test_extra_columns_ignored(self):
        csv_data = "date,symbol,action,price,shares,notes,broker\n2024-01-15,AAPL,BUY,185.50,10,entry,TD\n"
        result = parse_detailed(csv_data)
        assert len(result) == 1
        assert "notes" not in result[0]

    def test_missing_column_raises(self):
        csv_data = "date,symbol,action,price\n2024-01-15,AAPL,BUY,185.50\n"
        with pytest.raises(ValueError, match="missing required columns"):
            parse_detailed(csv_data)

    def test_empty_csv_raises(self):
        with pytest.raises(ValueError):
            parse_detailed("")


class TestParseDetailedDateValidation:
    def test_slash_format_raises(self):
        csv_data = "date,symbol,action,price,shares\n01/15/2024,AAPL,BUY,185.50,10\n"
        with pytest.raises(ValueError, match="Row 2: invalid date"):
            parse_detailed(csv_data)

    def test_missing_leading_zero_raises(self):
        csv_data = "date,symbol,action,price,shares\n2024-1-5,AAPL,BUY,185.50,10\n"
        with pytest.raises(ValueError, match="Row 2: invalid date"):
            parse_detailed(csv_data)

    def test_error_message_includes_bad_value(self):
        bad_date = "15-01-2024"
        csv_data = f"date,symbol,action,price,shares\n{bad_date},AAPL,BUY,185.50,10\n"
        with pytest.raises(ValueError, match=bad_date):
            parse_detailed(csv_data)


class TestParseDetailedActionValidation:
    def test_lowercase_buy_normalized(self):
        csv_data = "date,symbol,action,price,shares\n2024-01-15,AAPL,buy,185.50,10\n"
        result = parse_detailed(csv_data)
        assert result[0]["action"] == "BUY"

    def test_mixed_case_sell_normalized(self):
        csv_data = "date,symbol,action,price,shares\n2024-01-15,AAPL,Sell,185.50,10\n"
        result = parse_detailed(csv_data)
        assert result[0]["action"] == "SELL"

    def test_invalid_action_raises(self):
        csv_data = "date,symbol,action,price,shares\n2024-01-15,AAPL,HOLD,185.50,10\n"
        with pytest.raises(ValueError, match="Row 2: action 'HOLD' is not BUY or SELL"):
            parse_detailed(csv_data)

    def test_blank_action_raises(self):
        csv_data = "date,symbol,action,price,shares\n2024-01-15,AAPL,,185.50,10\n"
        with pytest.raises(ValueError, match="Row 2: action is blank"):
            parse_detailed(csv_data)


class TestParseDetailedPriceValidation:
    def test_zero_price_raises(self):
        csv_data = "date,symbol,action,price,shares\n2024-01-15,AAPL,BUY,0,10\n"
        with pytest.raises(ValueError, match="price must be positive"):
            parse_detailed(csv_data)

    def test_negative_price_raises(self):
        csv_data = "date,symbol,action,price,shares\n2024-01-15,AAPL,BUY,-5.00,10\n"
        with pytest.raises(ValueError, match="price must be positive"):
            parse_detailed(csv_data)

    def test_non_numeric_price_raises(self):
        csv_data = "date,symbol,action,price,shares\n2024-01-15,AAPL,BUY,N/A,10\n"
        with pytest.raises(ValueError, match="Row 2: price 'N/A' is not a number"):
            parse_detailed(csv_data)

    def test_inf_price_raises(self):
        csv_data = "date,symbol,action,price,shares\n2024-01-15,AAPL,BUY,inf,10\n"
        with pytest.raises(ValueError, match="price must be positive"):
            parse_detailed(csv_data)

    def test_nan_price_raises(self):
        csv_data = "date,symbol,action,price,shares\n2024-01-15,AAPL,BUY,nan,10\n"
        with pytest.raises(ValueError, match="price must be positive"):
            parse_detailed(csv_data)


class TestParseDetailedSharesValidation:
    def test_zero_shares_raises(self):
        csv_data = "date,symbol,action,price,shares\n2024-01-15,AAPL,BUY,185.50,0\n"
        with pytest.raises(ValueError, match="shares must be positive"):
            parse_detailed(csv_data)

    def test_negative_shares_raises(self):
        csv_data = "date,symbol,action,price,shares\n2024-01-15,AAPL,BUY,185.50,-1\n"
        with pytest.raises(ValueError, match="shares must be positive"):
            parse_detailed(csv_data)

    def test_non_numeric_shares_raises(self):
        csv_data = "date,symbol,action,price,shares\n2024-01-15,AAPL,BUY,185.50,ten\n"
        with pytest.raises(ValueError, match="Row 2: shares 'ten' is not a number"):
            parse_detailed(csv_data)

    def test_inf_shares_raises(self):
        csv_data = "date,symbol,action,price,shares\n2024-01-15,AAPL,BUY,185.50,inf\n"
        with pytest.raises(ValueError, match="shares must be positive"):
            parse_detailed(csv_data)

    def test_nan_shares_raises(self):
        csv_data = "date,symbol,action,price,shares\n2024-01-15,AAPL,BUY,185.50,nan\n"
        with pytest.raises(ValueError, match="shares must be positive"):
            parse_detailed(csv_data)


class TestParseDetailedSymbolValidation:
    def test_blank_symbol_raises(self):
        csv_data = "date,symbol,action,price,shares\n2024-01-15,,BUY,185.50,10\n"
        with pytest.raises(ValueError, match="Row 2: symbol is blank"):
            parse_detailed(csv_data)

    def test_lowercase_symbol_uppercased(self):
        csv_data = "date,symbol,action,price,shares\n2024-01-15,aapl,BUY,185.50,10\n"
        result = parse_detailed(csv_data)
        assert result[0]["symbol"] == "AAPL"

    def test_symbol_with_dot_accepted(self):
        csv_data = "date,symbol,action,price,shares\n2024-01-15,BRK.B,BUY,200.00,5\n"
        result = parse_detailed(csv_data)
        assert result[0]["symbol"] == "BRK.B"

    def test_symbol_with_hyphen_accepted(self):
        csv_data = "date,symbol,action,price,shares\n2024-01-15,BRK-B,BUY,200.00,5\n"
        result = parse_detailed(csv_data)
        assert result[0]["symbol"] == "BRK-B"

    def test_symbol_with_special_chars_raises(self):
        bad_symbols = [
            "AAPL!",   # special char
            "123",     # digits only
            "AAPL.",   # trailing dot
            "AA PL",   # space
            "A" * 21,  # too long
        ]
        for bad in bad_symbols:
            csv_data = f"date,symbol,action,price,shares\n2024-01-15,{bad},BUY,185.50,10\n"
            with pytest.raises(ValueError, match="invalid characters"):
                parse_detailed(csv_data)
        # Empty string triggers 'symbol is blank'
        csv_data = "date,symbol,action,price,shares\n2024-01-15,,BUY,185.50,10\n"
        with pytest.raises(ValueError, match="symbol is blank"):
            parse_detailed(csv_data)


class TestParseDetailedBlankRows:
    def test_blank_row_in_middle_skipped(self):
        csv_data = "date,symbol,action,price,shares\n2024-01-15,AAPL,BUY,185.50,10\n,,,,\n2024-02-20,AAPL,SELL,195.20,10\n"
        result = parse_detailed(csv_data)
        assert len(result) == 2


class TestParseDetailedFreeTierLimit:
    def test_over_limit_raises(self):
        header = "date,symbol,action,price,shares\n"
        rows = "".join(
            f"2024-01-{(i % 28) + 1:02d},AAPL,BUY,100.00,1\n"
            for i in range(FREE_TIER_TRADE_LIMIT + 1)
        )
        with pytest.raises(FreeTierLimitExceeded, match=f"exceeds the free tier limit of {FREE_TIER_TRADE_LIMIT}"):
            parse_detailed(header + rows)
    def test_unrelated_value_error_not_caught_as_limit(self):
        # Missing required column should raise ValueError, not FreeTierLimitExceeded
        bad_csv = "date,symbol,action,price\n2024-01-15,AAPL,BUY,185.50\n"
        with pytest.raises(ValueError) as excinfo:
            parse_detailed(bad_csv)
        assert "missing required columns" in str(excinfo.value)

    def test_exactly_at_limit_passes(self):
        header = "date,symbol,action,price,shares\n"
        rows = "".join(
            f"2024-01-{(i % 28) + 1:02d},AAPL,BUY,100.00,1\n"
            for i in range(FREE_TIER_TRADE_LIMIT)
        )
        result = parse_detailed(header + rows)
        assert len(result) == FREE_TIER_TRADE_LIMIT

    def test_blank_rows_after_limit_not_counted(self):
        # 100 valid trades followed by blank rows must not raise
        header = "date,symbol,action,price,shares\n"
        rows = "".join(
            f"2024-01-{(i % 28) + 1:02d},AAPL,BUY,100.00,1\n"
            for i in range(FREE_TIER_TRADE_LIMIT)
        )
        trailing_blanks = ",,,,\n,,,,\n"
        result = parse_detailed(header + rows + trailing_blanks)
        assert len(result) == FREE_TIER_TRADE_LIMIT


class TestParseDetailedWhitespaceCells:
    def test_whitespace_padded_data_cells_parsed(self):
        csv_data = "date,symbol,action,price,shares\n  2024-01-15  ,  AAPL  ,  BUY  ,  185.50  ,  10  \n"
        result = parse_detailed(csv_data)
        assert len(result) == 1
        assert result[0]["date"] == "2024-01-15"
        assert result[0]["symbol"] == "AAPL"
        assert result[0]["action"] == "BUY"
        assert result[0]["price"] == 185.50
        assert result[0]["shares"] == 10.0


class TestParseDetailedRaggedRows:
    def test_short_row_raises_value_error(self):
        # DictReader fills missing trailing cells with None; must raise a clear ValueError
        csv_data = "date,symbol,action,price,shares\n2024-01-15,AAPL\n"
        with pytest.raises(ValueError) as excinfo:
            parse_detailed(csv_data)
        assert "Row 2" in str(excinfo.value)

    def test_short_row_missing_only_last_field_raises(self):
        csv_data = "date,symbol,action,price,shares\n2024-01-15,AAPL,BUY,185.50\n"
        with pytest.raises(ValueError) as excinfo:
            parse_detailed(csv_data)
        assert "Row 2" in str(excinfo.value)


class TestAnalyzeUploadedTradesDetailed:
    def test_empty_file_returns_error(self):
        result = analyze_uploaded_trades("")
        assert "error" in result
        assert result["trades"] == []
        assert isinstance(result["warnings"], list)

    def test_bad_file_returns_error(self):
        # Missing required columns
        bad_csv = "date,symbol,action,price\n2024-01-15,AAPL,BUY,185.50\n"
        result = analyze_uploaded_trades(bad_csv)
        assert "error" in result
        assert result["trades"] == []
        assert isinstance(result["warnings"], list)

    _VALID_CSV = (
        "date,symbol,action,price,shares\n"
        "2024-01-15,AAPL,BUY,185.50,10\n"
        "2024-02-20,AAPL,SELL,195.20,10\n"
    )

    def test_returns_format_detailed(self):
        result = analyze_uploaded_trades(self._VALID_CSV)
        assert result["format"] == "detailed"

    def test_returns_trades_list(self):
        result = analyze_uploaded_trades(self._VALID_CSV)
        assert isinstance(result["trades"], list)
        assert len(result["trades"]) == 2

    def test_returns_warnings_list(self):
        result = analyze_uploaded_trades(self._VALID_CSV)
        assert isinstance(result["warnings"], list)

    def test_no_data_quality_warnings_for_clean_trades(self):
        # Clean data produces no duplicate/pairing warnings; only the trade count and concentration warnings are expected
        result = analyze_uploaded_trades(self._VALID_CSV)
        quality_warnings = [w for w in result["warnings"] if w["type"] not in {"insufficient_trade_count", "concentration_risk"}]
        assert quality_warnings == []
        # Also check that the concentration warning is present
        assert any(w["type"] == "concentration_risk" for w in result["warnings"])

    def test_returns_pnl_dict(self):
        result = analyze_uploaded_trades(self._VALID_CSV)
        assert isinstance(result["pnl"], dict)

    def test_returns_commissions_dict(self):
        result = analyze_uploaded_trades(self._VALID_CSV)
        assert isinstance(result["commissions"], dict)
        assert "total_commission_usd" in result["commissions"]
        assert "num_trades" in result["commissions"]

    def test_default_commission_is_zero_per_leg(self):
        # 2 trade legs (1 BUY + 1 SELL) × $0.00 default = $0.00
        result = analyze_uploaded_trades(self._VALID_CSV)
        assert result["commissions"]["total_commission_usd"] == pytest.approx(0.0)
        assert result["commissions"]["num_trades"] == 2

    def test_custom_commission_per_trade(self):
        # 2 trade legs × $4.95 = $9.90
        result = analyze_uploaded_trades(self._VALID_CSV, commission_per_trade=4.95)
        assert result["commissions"]["total_commission_usd"] == pytest.approx(9.90)

    def test_zero_commission_per_trade(self):
        result = analyze_uploaded_trades(self._VALID_CSV, commission_per_trade=0.0)
        assert result["commissions"]["total_commission_usd"] == pytest.approx(0.0)

    def test_unmatched_sell_surfaces_as_warning(self):
        csv_data = (
            "date,symbol,action,price,shares\n"
            "2024-01-15,AAPL,SELL,195.20,10\n"
        )
        result = analyze_uploaded_trades(csv_data)
        assert any(w["type"] == "unmatched_sell" for w in result["warnings"])


# ---------------------------------------------------------------------------
# Trade count sufficiency warnings
# ---------------------------------------------------------------------------

def _make_closed_trades(n: int) -> str:
    """Generate CSV with n matched BUY+SELL pairs for AAPL."""
    rows = ["date,symbol,action,price,shares"]
    for i in range(n):
        rows.append(f"2024-01-{(i % 28) + 1:02d},AAPL,BUY,100.00,10")
        rows.append(f"2024-02-{(i % 28) + 1:02d},AAPL,SELL,110.00,10")
    return "\n".join(rows) + "\n"


class TestTradeCountSufficiencyWarning:

    def test_fewer_than_30_closed_trades_warns(self):
        result = analyze_uploaded_trades(_make_closed_trades(5))
        warning = next((w for w in result["warnings"] if w["type"] == "insufficient_trade_count"), None)
        assert warning is not None
        assert warning["count"] == 5

    def test_29_closed_trades_warns(self):
        result = analyze_uploaded_trades(_make_closed_trades(29))
        warning = next((w for w in result["warnings"] if w["type"] == "insufficient_trade_count"), None)
        assert warning is not None
        assert warning["count"] == 29

    def test_exactly_30_closed_trades_no_warn(self):
        result = analyze_uploaded_trades(_make_closed_trades(30))
        assert not any(w["type"] == "insufficient_trade_count" for w in result["warnings"])

    def test_more_than_30_closed_trades_no_warn(self):
        result = analyze_uploaded_trades(_make_closed_trades(31))
        assert not any(w["type"] == "insufficient_trade_count" for w in result["warnings"])

    def test_warning_has_correct_structure(self):
        result = analyze_uploaded_trades(_make_closed_trades(1))
        warning = next(w for w in result["warnings"] if w["type"] == "insufficient_trade_count")
        assert warning["level"] == "warning"
        assert "30" in warning["message"]
        assert warning["count"] == 1

    def test_zero_closed_trades_warns(self):
        # Only BUY rows — no closed trades
        csv_data = "date,symbol,action,price,shares\n2024-01-15,AAPL,BUY,100.00,10\n"
        result = analyze_uploaded_trades(csv_data)
        warning = next((w for w in result["warnings"] if w["type"] == "insufficient_trade_count"), None)
        assert warning is not None
        assert warning["count"] == 0


def test_non_numeric_commission_per_trade_rejected(client):
    # Simulate a Flask test client POST with a non-numeric commission
    response = client.post(
        '/analyze-trades',
        json={
            "csv_data": VALID_CSV,
            "commission_per_trade": "notanumber"
        }
    )
    assert response.status_code == 400
    assert "commission_per_trade must be a number" in response.get_json().get("error", "")


def test_negative_commission_per_trade_rejected(client):
    response = client.post(
        '/analyze-trades',
        json={
            "csv_data": VALID_CSV,
            "commission_per_trade": -5
        }
    )
    assert response.status_code == 400
    assert "commission_per_trade must be a non-negative number" in response.get_json().get("error", "")
