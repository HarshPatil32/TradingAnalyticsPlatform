"""Tests for validate_trades() and calculate_pnl() in csv_analyzer."""
import pytest

from csv_analyzer import validate_trades, calculate_pnl, check_concentration_risk


def _trade(date, symbol, action, price, shares):
    return {"date": date, "symbol": symbol, "action": action, "price": price, "shares": shares}


# ---------------------------------------------------------------------------
# validate_trades
# ---------------------------------------------------------------------------

class TestValidateTrades:
    def test_duplicate_case_insensitive(self):
        # Should detect duplicate even if action/symbol case differs
        trade1 = _trade("2024-01-01", "aapl", "buy", 100.0, 10)
        trade2 = _trade("2024-01-01", "AAPL", "BUY", 105.0, 5)
        warnings = validate_trades([trade1, trade2])
        assert any(w["type"] == "duplicate" for w in warnings)

    def test_duplicate_symbol_whitespace(self):
        # Should detect duplicate even if symbol has extra whitespace
        trade1 = _trade("2024-01-01", "AAPL ", "BUY", 100.0, 10)
        trade2 = _trade("2024-01-01", "AAPL", "BUY", 105.0, 5)
        warnings = validate_trades([trade1, trade2])
        assert any(w["type"] == "duplicate" for w in warnings)

    def test_multiple_duplicates_only_one_warning(self):
        # Three identical trades should produce one warning with count=3
        trade1 = _trade("2024-01-01", "AAPL", "BUY", 100.0, 10)
        trade2 = _trade("2024-01-01", "AAPL", "BUY", 105.0, 5)
        trade3 = _trade("2024-01-01", "AAPL", "BUY", 110.0, 2)
        warnings = [w for w in validate_trades([trade1, trade2, trade3]) if w["type"] == "duplicate"]
        assert len(warnings) == 1
        assert "appears 3 times" in warnings[0]["message"]

    def test_sell_lowercase_action_flagged(self):
        trades = [
            {"date": "2024-01-02", "symbol": "AAPL", "action": "sell", "price": 110.0, "shares": 10},
        ]
        warnings = validate_trades(trades)
        assert any(w["type"] == "unmatched_sell" and w["level"] == "warning" for w in warnings)

    def test_symbol_with_whitespace_still_matched(self):
        trades = [
            {"date": "2024-01-01", "symbol": "AAPL ", "action": "BUY", "price": 100.0, "shares": 10},
            {"date": "2024-01-02", "symbol": "AAPL", "action": "SELL", "price": 110.0, "shares": 10},
        ]
        warnings = validate_trades(trades)
        assert not any(w["type"] == "unmatched_sell" for w in warnings)

    def test_sell_missing_date_field(self):
        trades = [
            {"symbol": "AAPL", "action": "SELL", "price": 110.0, "shares": 10},
        ]
        warnings = validate_trades(trades)
        assert any(w["type"] == "unmatched_sell" and "unknown date" in w["message"] for w in warnings)

    def test_missing_level_key_defaults_to_warning(self):
        # Simulate a trade warning without a level key
        items = [
            {"type": "duplicate", "message": "dup"},
            {"type": "unmatched_sell", "message": "sell"},
        ]
        # Patch analyze_uploaded_trades to use these items
        from csv_analyzer import analyze_uploaded_trades
        def fake_validate_trades(_):
            return items
        import csv_analyzer
        orig = csv_analyzer.validate_trades
        csv_analyzer.validate_trades = fake_validate_trades
        try:
            result = analyze_uploaded_trades("date,symbol,action,price,shares\n")
            assert "notices" in result
            # Only validate_trades-sourced warnings; trade count warning may also appear
            validate_types = {"duplicate", "unmatched_sell", "insufficient_trade_count"}
            assert all(w["type"] in validate_types for w in result["warnings"])
        finally:
            csv_analyzer.validate_trades = orig

    def test_zero_price_flagged(self):
        trades = [_trade("2024-01-01", "AAPL", "BUY", 0, 10)]
        warnings = validate_trades(trades)
        assert any(w["type"] == "invalid_price" and w["level"] == "warning" for w in warnings)

    def test_negative_price_flagged(self):
        trades = [_trade("2024-01-01", "AAPL", "BUY", -5.0, 10)]
        warnings = validate_trades(trades)
        assert any(w["type"] == "invalid_price" and w["level"] == "warning" for w in warnings)

    def test_zero_shares_flagged(self):
        trades = [_trade("2024-01-01", "AAPL", "BUY", 100.0, 0)]
        warnings = validate_trades(trades)
        assert any(w["type"] == "invalid_shares" and w["level"] == "warning" for w in warnings)

    def test_negative_shares_flagged(self):
        trades = [_trade("2024-01-01", "AAPL", "BUY", 100.0, -5)]
        warnings = validate_trades(trades)
        assert any(w["type"] == "invalid_shares" and w["level"] == "warning" for w in warnings)

    def test_valid_trade_no_invalid_value_warnings(self):
        trades = [_trade("2024-01-01", "AAPL", "BUY", 150.0, 10)]
        warnings = validate_trades(trades)
        assert not any(w["type"] in {"invalid_price", "invalid_shares"} for w in warnings)

    def test_both_price_and_shares_invalid(self):
        trades = [_trade("2024-01-01", "MSFT", "BUY", 0, 0)]
        warnings = validate_trades(trades)
        assert any(w["type"] == "invalid_price" for w in warnings)
        assert any(w["type"] == "invalid_shares" for w in warnings)

    def test_invalid_price_warning_contains_symbol_and_date(self):
        trades = [_trade("2024-03-15", "TSLA", "BUY", -1.0, 5)]
        warnings = validate_trades(trades)
        match = next(w for w in warnings if w["type"] == "invalid_price")
        assert "TSLA" in match["message"]
        assert "2024-03-15" in match["message"]

    def test_analyze_uploaded_trades_returns_notices_key(self):
        from csv_analyzer import analyze_uploaded_trades
        csv = "date,symbol,action,price,shares\n2024-01-01,AAPL,BUY,100,10\n2024-02-01,AAPL,SELL,110,10\n"
        result = analyze_uploaded_trades(csv)
        assert "notices" in result
        assert isinstance(result["notices"], list)

    def test_no_open_positions_empty_notices(self):
        from csv_analyzer import analyze_uploaded_trades
        csv = "date,symbol,action,price,shares\n2024-01-01,AAPL,BUY,100,10\n2024-02-01,AAPL,SELL,110,10\n"
        result = analyze_uploaded_trades(csv)
        assert result["notices"] == []
    def test_no_warnings_for_clean_trades(self):
        trades = [
            _trade("2024-01-01", "AAPL", "BUY", 100.0, 10),
            _trade("2024-02-01", "AAPL", "SELL", 110.0, 10),
        ]
        assert validate_trades(trades) == []

    def test_duplicate_trade_warns(self):
        trade = _trade("2024-01-01", "AAPL", "BUY", 100.0, 10)
        warnings = validate_trades([trade, trade])
        assert any(w["type"] == "duplicate" for w in warnings)

    def test_unmatched_sell_warns(self):
        trades = [_trade("2024-01-01", "AAPL", "SELL", 110.0, 10)]
        warnings = validate_trades(trades)
        assert any(w["type"] == "unmatched_sell" for w in warnings)

    def test_unclosed_position_is_info_not_warning(self):
        trades = [_trade("2024-01-01", "AAPL", "BUY", 100.0, 10)]
        items = validate_trades(trades)
        unclosed = [i for i in items if i["type"] == "unclosed_position"]
        assert len(unclosed) == 1
        assert unclosed[0]["level"] == "info"

    def test_unclosed_position_warns(self):
        trades = [_trade("2024-01-01", "AAPL", "BUY", 100.0, 10)]
        warnings = validate_trades(trades)
        assert any(w["type"] == "unclosed_position" for w in warnings)

    def test_duplicate_has_warning_level(self):
        trade = _trade("2024-01-01", "AAPL", "BUY", 100.0, 10)
        items = validate_trades([trade, trade])
        duplicates = [i for i in items if i["type"] == "duplicate"]
        assert all(d["level"] == "warning" for d in duplicates)

    def test_unmatched_sell_has_warning_level(self):
        trades = [_trade("2024-01-01", "AAPL", "SELL", 110.0, 10)]
        items = validate_trades(trades)
        unmatched = [i for i in items if i["type"] == "unmatched_sell"]
        assert all(u["level"] == "warning" for u in unmatched)

    def test_open_position_message_is_informational(self):
        trades = [_trade("2024-01-15", "TSLA", "BUY", 200.0, 5)]
        items = validate_trades(trades)
        unclosed = [i for i in items if i["type"] == "unclosed_position"]
        assert len(unclosed) == 1
        assert "TSLA" in unclosed[0]["message"]
        assert "2024-01-15" in unclosed[0]["message"]

    def test_unclosed_position_has_structured_fields(self):
        trades = [_trade("2024-01-15", "AAPL", "BUY", 150.0, 10)]
        items = validate_trades(trades)
        unclosed = [i for i in items if i["type"] == "unclosed_position"]
        assert len(unclosed) == 1
        notice = unclosed[0]
        assert notice["symbol"] == "AAPL"
        assert notice["date"] == "2024-01-15"
        assert notice["price"] == 150.0
        assert notice["shares"] == 10

    def test_multiple_unclosed_positions_have_structured_fields(self):
        trades = [
            _trade("2024-01-01", "AAPL", "BUY", 100.0, 10),
            _trade("2024-01-02", "MSFT", "BUY", 200.0, 5),
        ]
        items = validate_trades(trades)
        unclosed = [i for i in items if i["type"] == "unclosed_position"]
        assert len(unclosed) == 2
        by_symbol = {n["symbol"]: n for n in unclosed}
        assert by_symbol["AAPL"]["date"] == "2024-01-01"
        assert by_symbol["AAPL"]["price"] == 100.0
        assert by_symbol["AAPL"]["shares"] == 10
        assert by_symbol["MSFT"]["date"] == "2024-01-02"
        assert by_symbol["MSFT"]["price"] == 200.0
        assert by_symbol["MSFT"]["shares"] == 5

    def test_analyze_uploaded_trades_unclosed_position_has_structured_fields(self):
        from csv_analyzer import analyze_uploaded_trades
        csv = "date,symbol,action,price,shares\n2024-01-15,AAPL,BUY,150,10\n"
        result = analyze_uploaded_trades(csv)
        assert len(result["notices"]) == 1
        notice = result["notices"][0]
        assert notice["type"] == "unclosed_position"
        assert notice["symbol"] == "AAPL"
        assert notice["price"] == 150.0
        assert notice["shares"] == 10

    def test_multiple_symbols_paired_independently(self):
        trades = [
            _trade("2024-01-01", "AAPL", "BUY", 100.0, 10),
            _trade("2024-01-01", "MSFT", "BUY", 200.0, 5),
            _trade("2024-02-01", "AAPL", "SELL", 110.0, 10),
            _trade("2024-02-01", "MSFT", "SELL", 210.0, 5),
        ]
        assert validate_trades(trades) == []


# --- Module-level tests for edge cases and new metrics ---
def test_mixed_case_sell_actions_no_warnings():
    trades = [
        _trade("2024-01-01", "AAPL", "BUY", 100.0, 10),
        _trade("2024-02-01", "AAPL", "sell", 110.0, 10),
    ]
    assert validate_trades(trades) == []

def test_mixed_case_sell_duplicate_detected():
    trade = _trade("2024-01-01", "AAPL", "SELL", 100.0, 10)
    same_lowercase = _trade("2024-01-01", "AAPL", "sell", 100.0, 10)
    warnings = validate_trades([trade, same_lowercase])
    assert any(w["type"] == "duplicate" for w in warnings)

def test_missing_action_does_not_crash():
    trades = [
        {"date": "2024-01-01", "symbol": "AAPL", "price": 100.0, "shares": 10},
        _trade("2024-02-01", "AAPL", "SELL", 110.0, 10),
    ]
    warnings = validate_trades(trades)
    assert isinstance(warnings, list)

def test_null_action_does_not_crash():
    trades = [
        {"date": "2024-01-01", "symbol": "AAPL", "action": None, "price": 100.0, "shares": 10},
        _trade("2024-02-01", "AAPL", "SELL", 110.0, 10),
    ]
    warnings = validate_trades(trades)
    assert isinstance(warnings, list)

def test_mixed_case_sell_actions_compute_correctly():
    trades = [
        _trade("2024-01-01", "AAPL", "BUY", 100.0, 10),
        _trade("2024-02-01", "AAPL", "sell", 110.0, 10),
    ]
    result = calculate_pnl(trades)
    assert result["total_pnl"] == 100.0
    assert len(result["trade_pnl"]) == 1

def test_missing_action_skipped_in_pnl():
    trades = [
        {"date": "2024-01-01", "symbol": "AAPL", "price": 100.0, "shares": 10},
        _trade("2024-02-01", "AAPL", "SELL", 110.0, 10),
    ]
    result = calculate_pnl(trades)
    assert result["total_pnl"] == 0.0
    assert result["trade_pnl"] == []

def test_null_action_skipped_in_pnl():
    trades = [
        {"date": "2024-01-01", "symbol": "AAPL", "action": None, "price": 100.0, "shares": 10},
        _trade("2024-02-01", "AAPL", "SELL", 110.0, 10),
    ]
    result = calculate_pnl(trades)
    assert result["total_pnl"] == 0.0
    assert result["trade_pnl"] == []

def test_same_date_symbol_different_action_not_duplicate():
    # BUY and SELL on same date+symbol are not duplicates
    trade1 = _trade("2024-01-01", "AAPL", "BUY", 100.0, 10)
    trade2 = _trade("2024-01-01", "AAPL", "SELL", 100.0, 10)
    warnings = validate_trades([trade1, trade2])
    assert not any(w["type"] == "duplicate" for w in warnings)


def test_multiple_sells_no_buy_each_flagged():
    # Two SELLs for the same symbol with no BUY — both should be flagged
    trades = [
        _trade("2024-01-01", "AAPL", "SELL", 110.0, 10),
        _trade("2024-01-02", "AAPL", "SELL", 115.0, 10),
    ]
    warnings = validate_trades(trades)
    unmatched = [w for w in warnings if w["type"] == "unmatched_sell"]
    assert len(unmatched) == 2
    assert all(w["level"] == "warning" for w in unmatched)


def test_more_sells_than_buys_extra_sell_flagged():
    # One BUY consumed by first SELL; second SELL has no BUY left
    trades = [
        _trade("2024-01-01", "AAPL", "BUY", 100.0, 10),
        _trade("2024-02-01", "AAPL", "SELL", 110.0, 10),
        _trade("2024-03-01", "AAPL", "SELL", 120.0, 10),
    ]
    warnings = validate_trades(trades)
    unmatched = [w for w in warnings if w["type"] == "unmatched_sell"]
    assert len(unmatched) == 1
    assert "2024-03-01" in unmatched[0]["message"]
    assert unmatched[0]["level"] == "warning"


# ---------------------------------------------------------------------------
# calculate_pnl
# ---------------------------------------------------------------------------

class TestCalculatePnl:
    def test_single_profitable_trade(self):
        trades = [
            _trade("2024-01-01", "AAPL", "BUY", 100.0, 10),
            _trade("2024-02-01", "AAPL", "SELL", 110.0, 10),
        ]
        result = calculate_pnl(trades)
        assert result["total_pnl"] == 100.0  # (110-100)*10

    def test_single_losing_trade(self):
        trades = [
            _trade("2024-01-01", "AAPL", "BUY", 110.0, 10),
            _trade("2024-02-01", "AAPL", "SELL", 100.0, 10),
        ]
        result = calculate_pnl(trades)
        assert result["total_pnl"] == -100.0

    def test_trade_pnl_list_length(self):
        trades = [
            _trade("2024-01-01", "AAPL", "BUY", 100.0, 10),
            _trade("2024-02-01", "AAPL", "SELL", 110.0, 10),
        ]
        result = calculate_pnl(trades)
        assert len(result["trade_pnl"]) == 1

    def test_equity_curve_matches_trade_pnl_count(self):
        trades = [
            _trade("2024-01-01", "AAPL", "BUY", 100.0, 10),
            _trade("2024-02-01", "AAPL", "SELL", 110.0, 10),
        ]
        result = calculate_pnl(trades)
        assert len(result["equity_curve"]) == len(result["trade_pnl"])

    def test_total_return_pct_positive(self):
        trades = [
            _trade("2024-01-01", "AAPL", "BUY", 100.0, 10),
            _trade("2024-02-01", "AAPL", "SELL", 110.0, 10),
        ]
        result = calculate_pnl(trades)
        # P&L = 100, cost = 1000, return = 10%
        assert result["total_return_pct"] == 10.0

    def test_unmatched_sell_skipped(self):
        # A SELL with no prior BUY should not crash and should not appear in trade_pnl
        trades = [_trade("2024-01-01", "AAPL", "SELL", 110.0, 10)]
        result = calculate_pnl(trades)
        assert result["trade_pnl"] == []
        assert result["total_pnl"] == 0.0

    def test_empty_trades(self):
        result = calculate_pnl([])
        assert result["total_pnl"] == 0.0
        assert result["trade_pnl"] == []
        assert result["equity_curve"] == []
        assert result["total_return_pct"] == 0.0

    def test_fifo_pairing_multiple_buys(self):
        # Two buys at different prices; sells should match in FIFO order
        trades = [
            _trade("2024-01-01", "AAPL", "BUY", 100.0, 10),
            _trade("2024-01-15", "AAPL", "BUY", 120.0, 10),
            _trade("2024-02-01", "AAPL", "SELL", 130.0, 10),  # matches first BUY @ 100
        ]
        result = calculate_pnl(trades)
        assert result["trade_pnl"][0]["buy_price"] == 100.0
        assert result["trade_pnl"][0]["pnl"] == 300.0  # (130-100)*10

    def test_cumulative_pnl_accumulates(self):
        trades = [
            _trade("2024-01-01", "AAPL", "BUY", 100.0, 10),
            _trade("2024-02-01", "AAPL", "SELL", 110.0, 10),  # +100
            _trade("2024-03-01", "MSFT", "BUY", 200.0, 5),
            _trade("2024-04-01", "MSFT", "SELL", 220.0, 5),   # +100
        ]
        result = calculate_pnl(trades)
        assert result["total_pnl"] == 200.0
        assert result["equity_curve"][-1]["cumulative_pnl"] == 200.0

    def test_equity_curve_is_chronological_when_sells_are_out_of_order(self):
        # CSV has valid BUY->SELL pairing but sell rows are not chronological.
        trades = [
            _trade("2024-01-01", "AAPL", "BUY", 100.0, 10),
            _trade("2024-02-01", "MSFT", "BUY", 200.0, 5),
            _trade("2024-04-01", "MSFT", "SELL", 220.0, 5),   # +100, later close
            _trade("2024-03-01", "AAPL", "SELL", 110.0, 10),  # +100, earlier close
        ]
        result = calculate_pnl(trades)
        dates = [point["date"] for point in result["equity_curve"]]
        assert dates == ["2024-03-01", "2024-04-01"]
        assert result["equity_curve"][0]["cumulative_pnl"] == 100.0
        assert result["equity_curve"][1]["cumulative_pnl"] == 200.0

    def test_result_is_float_or_none(self):
        trades = [
            _trade("2024-01-01", "AAPL", "BUY", 100.0, 10),
            _trade("2024-02-01", "AAPL", "SELL", 110.0, 10),
        ]
        result = calculate_pnl(trades)
        assert isinstance(result["avg_holding_days_winners"], float)

    def test_no_trades_returns_none(self):
        result = calculate_pnl([])
        assert result["avg_holding_days_winners"] is None

    def test_all_losses_returns_none(self):
        trades = [
            _trade("2024-01-01", "AAPL", "BUY", 110.0, 10),
            _trade("2024-02-01", "AAPL", "SELL", 100.0, 10),
        ]
        result = calculate_pnl(trades)
        assert result["avg_holding_days_winners"] is None

    def test_single_winner_returns_correct_days(self):
        trades = [
            _trade("2024-01-01", "AAPL", "BUY", 100.0, 10),
            _trade("2024-02-01", "AAPL", "SELL", 110.0, 10),
        ]
        result = calculate_pnl(trades)
        assert result["avg_holding_days_winners"] == 31.0

    def test_same_day_buy_sell_zero_days(self):
        trades = [
            _trade("2024-01-01", "AAPL", "BUY", 100.0, 10),
            _trade("2024-01-01", "AAPL", "SELL", 110.0, 10),
        ]
        result = calculate_pnl(trades)
        assert result["avg_holding_days_winners"] == 0.0

    def test_mixed_case_sell_actions_compute_correctly(self):
        trades = [
            _trade("2024-01-01", "AAPL", "BUY", 100.0, 10),
            _trade("2024-02-01", "AAPL", "sell", 110.0, 10),
        ]
        result = calculate_pnl(trades)
        assert result["total_pnl"] == 100.0
        assert len(result["trade_pnl"]) == 1

    def test_missing_action_skipped_in_pnl(self):
        trades = [
            {"date": "2024-01-01", "symbol": "AAPL", "price": 100.0, "shares": 10},
            _trade("2024-02-01", "AAPL", "SELL", 110.0, 10),
        ]
        result = calculate_pnl(trades)
        assert result["total_pnl"] == 0.0
        assert result["trade_pnl"] == []

    def test_null_action_skipped_in_pnl(self):
        trades = [
            {"date": "2024-01-01", "symbol": "AAPL", "action": None, "price": 100.0, "shares": 10},
            _trade("2024-02-01", "AAPL", "SELL", 110.0, 10),
        ]
        result = calculate_pnl(trades)
        assert result["total_pnl"] == 0.0
        assert result["trade_pnl"] == []

    # avg_holding_days_losers tests

    def test_no_trades_losers_returns_none(self):
        result = calculate_pnl([])
        assert result["avg_holding_days_losers"] is None

    def test_all_winners_losers_returns_none(self):
        trades = [
            _trade("2024-01-01", "AAPL", "BUY", 100.0, 10),
            _trade("2024-02-01", "AAPL", "SELL", 110.0, 10),
        ]
        result = calculate_pnl(trades)
        assert result["avg_holding_days_losers"] is None

    def test_single_loser_returns_correct_days(self):
        trades = [
            _trade("2024-01-01", "AAPL", "BUY", 110.0, 10),
            _trade("2024-02-01", "AAPL", "SELL", 100.0, 10),
        ]
        result = calculate_pnl(trades)
        assert result["avg_holding_days_losers"] == 31.0

    def test_losers_is_float(self):
        trades = [
            _trade("2024-01-01", "AAPL", "BUY", 110.0, 10),
            _trade("2024-02-01", "AAPL", "SELL", 100.0, 10),
        ]
        result = calculate_pnl(trades)
        assert isinstance(result["avg_holding_days_losers"], float)

    def test_breakeven_excluded_from_losers(self):
        # Breakeven trade (pnl == 0) should not be counted
        trades = [
            _trade("2024-01-01", "AAPL", "BUY", 100.0, 10),
            _trade("2024-02-01", "AAPL", "SELL", 100.0, 10),
        ]
        result = calculate_pnl(trades)
        assert result["avg_holding_days_losers"] is None

    def test_mean_holding_days_losers_multiple(self):
        # Loser 1: 10 days, Loser 2: 20 days -> mean = 15
        trades = [
            _trade("2024-01-01", "AAPL", "BUY", 110.0, 10),
            _trade("2024-01-11", "AAPL", "SELL", 100.0, 10),
            _trade("2024-02-01", "MSFT", "BUY", 200.0, 5),
            _trade("2024-02-21", "MSFT", "SELL", 190.0, 5),
        ]
        result = calculate_pnl(trades)
        assert result["avg_holding_days_losers"] == 15.0

    def test_same_day_buy_sell_loser_zero_days(self):
        trades = [
            _trade("2024-01-01", "AAPL", "BUY", 110.0, 10),
            _trade("2024-01-01", "AAPL", "SELL", 100.0, 10),
        ]
        result = calculate_pnl(trades)
        assert result["avg_holding_days_losers"] == 0.0

    def test_winners_and_losers_computed_independently(self):
        # Winner: 10 days, Loser: 20 days
        trades = [
            _trade("2024-01-01", "AAPL", "BUY", 100.0, 10),
            _trade("2024-01-11", "AAPL", "SELL", 110.0, 10),
            _trade("2024-02-01", "MSFT", "BUY", 200.0, 5),
            _trade("2024-02-21", "MSFT", "SELL", 190.0, 5),
        ]
        result = calculate_pnl(trades)
        assert result["avg_holding_days_winners"] == 10.0
        assert result["avg_holding_days_losers"] == 20.0

    def test_avg_holding_days_losers_missing_dates(self):
        # Should return None if dates are missing
        trades = [
            {"date": None, "symbol": "AAPL", "action": "BUY", "price": 110.0, "shares": 10},
            {"date": None, "symbol": "AAPL", "action": "SELL", "price": 100.0, "shares": 10},
        ]
        result = calculate_pnl(trades)
        assert result["avg_holding_days_losers"] is None


# ---------------------------------------------------------------------------
# check_concentration_risk
# ---------------------------------------------------------------------------

class TestCheckConcentrationRisk:
    def test_all_trades_one_symbol_warns(self):
        trades = [_trade("2024-01-01", "AAPL", "BUY", 100.0, 10)] * 4
        result = check_concentration_risk(trades)
        assert result is not None
        assert result["type"] == "concentration_risk"
        assert result["level"] == "warning"

    def test_warning_contains_symbol_name(self):
        trades = [_trade("2024-01-01", "AAPL", "BUY", 100.0, 10)] * 4
        result = check_concentration_risk(trades)
        assert "AAPL" in result["message"]

    def test_majority_in_one_symbol_warns(self):
        # 3 AAPL + 1 MSFT = 75% AAPL -> should warn
        trades = [
            _trade("2024-01-01", "AAPL", "BUY", 100.0, 10),
            _trade("2024-01-02", "AAPL", "SELL", 110.0, 10),
            _trade("2024-01-03", "AAPL", "BUY", 105.0, 10),
            _trade("2024-01-04", "MSFT", "BUY", 200.0, 5),
        ]
        result = check_concentration_risk(trades)
        assert result is not None
        assert result["symbol"] == "AAPL"
        assert result["concentration_pct"] == 0.75

    def test_exactly_50_percent_does_not_warn(self):
        # 2 AAPL + 2 MSFT = exactly 50% each -> no warning
        trades = [
            _trade("2024-01-01", "AAPL", "BUY", 100.0, 10),
            _trade("2024-01-02", "AAPL", "SELL", 110.0, 10),
            _trade("2024-01-03", "MSFT", "BUY", 200.0, 5),
            _trade("2024-01-04", "MSFT", "SELL", 210.0, 5),
        ]
        result = check_concentration_risk(trades)
        assert result is None

    def test_even_split_three_symbols_no_warning(self):
        trades = [
            _trade("2024-01-01", "AAPL", "BUY", 100.0, 10),
            _trade("2024-01-02", "MSFT", "BUY", 200.0, 5),
            _trade("2024-01-03", "TSLA", "BUY", 300.0, 2),
        ]
        result = check_concentration_risk(trades)
        assert result is None

    def test_single_trade_returns_none(self):
        trades = [_trade("2024-01-01", "AAPL", "BUY", 100.0, 10)]
        result = check_concentration_risk(trades)
        assert result is None

    def test_empty_trades_returns_none(self):
        result = check_concentration_risk([])
        assert result is None

    def test_result_has_required_keys(self):
        trades = [_trade("2024-01-01", "AAPL", "BUY", 100.0, 10)] * 3
        result = check_concentration_risk(trades)
        assert result is not None
        for key in ("type", "level", "message", "symbol", "trade_count", "total_trades", "concentration_pct"):
            assert key in result

    def test_trade_count_and_total_are_correct(self):
        trades = [
            _trade("2024-01-01", "AAPL", "BUY", 100.0, 10),
            _trade("2024-01-02", "AAPL", "SELL", 110.0, 10),
            _trade("2024-01-03", "AAPL", "BUY", 105.0, 10),
            _trade("2024-01-04", "MSFT", "BUY", 200.0, 5),
        ]
        result = check_concentration_risk(trades)
        assert result["trade_count"] == 3
        assert result["total_trades"] == 4

    def test_symbol_normalized_to_uppercase(self):
        trades = [
            {"date": "2024-01-01", "symbol": "aapl", "action": "BUY", "price": 100.0, "shares": 10},
            {"date": "2024-01-02", "symbol": "aapl", "action": "SELL", "price": 110.0, "shares": 10},
            {"date": "2024-01-03", "symbol": "aapl", "action": "BUY", "price": 105.0, "shares": 10},
            {"date": "2024-01-04", "symbol": "MSFT", "action": "BUY", "price": 200.0, "shares": 5},
        ]
        result = check_concentration_risk(trades)
        assert result is not None
        assert result["symbol"] == "AAPL"

    def test_trades_with_missing_symbol_are_skipped(self):
        # Trades with missing/empty symbol are skipped; only valid symbols are counted
        trades = [
            {"date": "2024-01-01", "symbol": None, "action": "BUY", "price": 100.0, "shares": 10},
            {"date": "2024-01-02", "symbol": "", "action": "BUY", "price": 100.0, "shares": 10},
            _trade("2024-01-03", "AAPL", "BUY", 100.0, 10),
            _trade("2024-01-04", "AAPL", "SELL", 110.0, 10),
            _trade("2024-01-05", "MSFT", "BUY", 200.0, 5),
        ]
        # 2 valid AAPL + 1 MSFT; missing-symbol trades not counted
        result = check_concentration_risk(trades)
        # 2/3 AAPL > 50%, so should warn
        assert result is not None
        assert result["symbol"] == "AAPL"
        assert result["total_trades"] == 3

    def test_all_trades_missing_symbol_returns_none(self):
        trades = [
            {"date": "2024-01-01", "symbol": None, "action": "BUY", "price": 100.0, "shares": 10},
            {"date": "2024-01-02", "symbol": "", "action": "BUY", "price": 100.0, "shares": 10},
        ]
        result = check_concentration_risk(trades)
        assert result is None

