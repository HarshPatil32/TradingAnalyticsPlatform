"""Tests for benchmark.fetch_benchmark and benchmark.compare_user_return_to_benchmarks."""

from datetime import datetime
from unittest.mock import patch

import numpy as np
import pandas as pd
import pytest

import benchmark as benchmark_module
from benchmark import (
    compare_user_return_to_benchmarks,
    fetch_benchmark,
    generate_verdict,
)


@pytest.fixture(autouse=True)
def clear_benchmark_cache():
    """Reset the module-level cache before every test so tests are isolated."""
    benchmark_module._cache.clear()
    yield
    benchmark_module._cache.clear()


_MOCK_YF = "benchmark.yf.download"


def _make_df(
    first: str, last: str, start_price: float, end_price: float
) -> pd.DataFrame:
    """Return a minimal price DataFrame with business-day DatetimeIndex."""
    dates = pd.bdate_range(start=first, end=last)
    prices = np.linspace(start_price, end_price, len(dates))
    return pd.DataFrame({"Close": prices}, index=dates)


def _sample_trades():
    return [
        {
            "date": "2023-01-03",
            "symbol": "AAPL",
            "action": "BUY",
            "price": 130.0,
            "shares": 10,
        },
        {
            "date": "2023-06-15",
            "symbol": "AAPL",
            "action": "SELL",
            "price": 180.0,
            "shares": 10,
        },
        {
            "date": "2023-12-15",
            "symbol": "MSFT",
            "action": "BUY",
            "price": 370.0,
            "shares": 5,
        },
    ]


class TestFetchBenchmark:
    @pytest.mark.parametrize("ticker", ["SPY", "QQQ"])
    @patch(_MOCK_YF)
    def test_returns_expected_keys(self, mock_dl, ticker):
        mock_dl.return_value = _make_df("2023-01-03", "2023-12-15", 400.0, 480.0)
        result = fetch_benchmark(_sample_trades(), ticker)
        assert result is not None
        assert set(result.keys()) == {
            "start_date",
            "end_date",
            "actual_start_date",
            "actual_end_date",
            "start_price",
            "end_price",
            "total_return_pct",
        }

    @pytest.mark.parametrize("ticker", ["SPY", "QQQ"])
    @patch(_MOCK_YF)
    def test_date_range_matches_trade_min_max(self, mock_dl, ticker):
        mock_dl.return_value = _make_df("2023-01-03", "2023-12-15", 400.0, 480.0)
        result = fetch_benchmark(_sample_trades(), ticker)
        assert result["start_date"] == "2023-01-03"
        assert result["end_date"] == "2023-12-15"

    @pytest.mark.parametrize("ticker", ["SPY", "QQQ"])
    @patch(_MOCK_YF)
    def test_total_return_pct_is_correct(self, mock_dl, ticker):
        start_price, end_price = 400.0, 480.0
        mock_dl.return_value = _make_df(
            "2023-01-03", "2023-12-15", start_price, end_price
        )
        result = fetch_benchmark(_sample_trades(), ticker)
        dates = pd.bdate_range(start="2023-01-03", end="2023-12-15")
        prices = np.linspace(start_price, end_price, len(dates))
        expected = round((prices[-1] - prices[0]) / prices[0] * 100, 4)
        assert result["total_return_pct"] == expected

    @pytest.mark.parametrize("ticker", ["SPY", "QQQ"])
    @patch(_MOCK_YF)
    def test_yfinance_called_with_correct_ticker_and_dates(self, mock_dl, ticker):
        mock_dl.return_value = _make_df("2023-01-03", "2023-12-15", 400.0, 480.0)
        fetch_benchmark(_sample_trades(), ticker)
        call_args = mock_dl.call_args
        assert call_args.args[0] == ticker
        assert call_args.kwargs["start"] == datetime(2023, 1, 3)
        # end should be one day after the last trade date (2023-12-16)
        assert call_args.kwargs["end"] == datetime(2023, 12, 16)

    @pytest.mark.parametrize("ticker", ["SPY", "QQQ"])
    def test_returns_none_for_empty_trades(self, ticker):
        result = fetch_benchmark([], ticker)
        assert result is None

    @pytest.mark.parametrize("ticker", ["SPY", "QQQ"])
    def test_returns_none_for_trades_with_no_dates(self, ticker):
        trades = [{"symbol": "AAPL", "action": "BUY", "price": 100.0, "shares": 1}]
        result = fetch_benchmark(trades, ticker)
        assert result is None

    @pytest.mark.parametrize("ticker", ["SPY", "QQQ"])
    @patch(_MOCK_YF)
    def test_returns_none_when_yfinance_returns_empty(self, mock_dl, ticker):
        mock_dl.return_value = pd.DataFrame()
        result = fetch_benchmark(_sample_trades(), ticker)
        assert result is None

    @pytest.mark.parametrize("ticker", ["SPY", "QQQ"])
    @patch(_MOCK_YF)
    def test_returns_none_when_yfinance_raises(self, mock_dl, ticker):
        mock_dl.side_effect = Exception("network error")
        result = fetch_benchmark(_sample_trades(), ticker)
        assert result is None

    @pytest.mark.parametrize("ticker", ["SPY", "QQQ"])
    @patch(_MOCK_YF)
    def test_single_trading_day_returns_none(self, mock_dl, ticker):
        # One row of data is below the minimum period threshold
        mock_dl.return_value = _make_df("2023-06-01", "2023-06-01", 440.0, 440.0)
        trades = [
            {
                "date": "2023-06-01",
                "symbol": "AAPL",
                "action": "BUY",
                "price": 180.0,
                "shares": 5,
            }
        ]
        result = fetch_benchmark(trades, ticker)
        assert result is None

    @pytest.mark.parametrize("ticker", ["SPY", "QQQ"])
    @patch(_MOCK_YF)
    def test_invalid_date_entries_are_skipped(self, mock_dl, ticker):
        mock_dl.return_value = _make_df("2023-01-03", "2023-06-15", 400.0, 450.0)
        trades = [
            {
                "date": "bad-date",
                "symbol": "X",
                "action": "BUY",
                "price": 1.0,
                "shares": 1,
            },
            {
                "date": "2023-01-03",
                "symbol": "X",
                "action": "BUY",
                "price": 1.0,
                "shares": 1,
            },
            {
                "date": "2023-06-15",
                "symbol": "X",
                "action": "SELL",
                "price": 2.0,
                "shares": 1,
            },
        ]
        result = fetch_benchmark(trades, ticker)
        assert result is not None
        assert result["start_date"] == "2023-01-03"
        assert result["end_date"] == "2023-06-15"

    @pytest.mark.parametrize("ticker", ["SPY", "QQQ"])
    @patch(_MOCK_YF)
    def test_partial_yfinance_data_still_returns_result(self, mock_dl, ticker):
        mock_dl.return_value = _make_df("2023-03-01", "2023-09-01", 400.0, 450.0)
        result = fetch_benchmark(_sample_trades(), ticker)
        assert result is not None
        assert result["start_date"] == "2023-01-03"
        assert result["end_date"] == "2023-12-15"
        assert isinstance(result["total_return_pct"], float)

    @pytest.mark.parametrize("ticker", ["SPY", "QQQ"])
    @patch(_MOCK_YF)
    def test_returns_none_when_start_price_is_zero(self, mock_dl, ticker):
        dates = pd.bdate_range(start="2023-01-03", end="2023-12-15")
        prices = [0.0] + [450.0] * (len(dates) - 1)
        mock_dl.return_value = pd.DataFrame({"Close": prices}, index=dates)
        result = fetch_benchmark(_sample_trades(), ticker)
        assert result is None

    @pytest.mark.parametrize("bad_ticker", ["", "   "])
    def test_empty_ticker_returns_none(self, bad_ticker):
        result = fetch_benchmark(_sample_trades(), bad_ticker)
        assert result is None

    @pytest.mark.parametrize("ticker", ["SPY", "QQQ"])
    @patch(_MOCK_YF)
    def test_ticker_passed_through_to_yfinance(self, mock_dl, ticker):
        mock_dl.return_value = _make_df("2023-01-03", "2023-12-15", 400.0, 480.0)
        fetch_benchmark(_sample_trades(), ticker)
        assert mock_dl.call_args.args[0] == ticker

    @pytest.mark.parametrize("ticker", ["SPY", "QQQ"])
    @patch(_MOCK_YF)
    def test_actual_dates_reflect_yfinance_data(self, mock_dl, ticker):
        # Data starts/ends on different days than the trade dates (e.g. holiday alignment)
        mock_dl.return_value = _make_df("2023-01-04", "2023-12-14", 400.0, 480.0)
        result = fetch_benchmark(_sample_trades(), ticker)
        assert result is not None
        assert result["start_date"] == "2023-01-03"  # original trade date
        assert result["end_date"] == "2023-12-15"  # original trade date
        assert result["actual_start_date"] == "2023-01-04"  # real trading day used
        assert result["actual_end_date"] == "2023-12-14"  # real trading day used

    @pytest.mark.parametrize("ticker", ["SPY", "QQQ"])
    @patch(_MOCK_YF)
    def test_result_is_cached_on_second_call(self, mock_dl, ticker):
        mock_dl.return_value = _make_df("2023-01-03", "2023-12-15", 400.0, 480.0)
        trades = _sample_trades()
        first = fetch_benchmark(trades, ticker)
        second = fetch_benchmark(trades, ticker)
        assert first == second
        assert mock_dl.call_count == 1  # yfinance called only once

    @pytest.mark.parametrize("ticker", ["SPY", "QQQ"])
    @patch(_MOCK_YF)
    def test_negative_return_is_computed_correctly(self, mock_dl, ticker):
        start_price, end_price = 480.0, 400.0
        mock_dl.return_value = _make_df(
            "2023-01-03", "2023-12-15", start_price, end_price
        )
        result = fetch_benchmark(_sample_trades(), ticker)
        assert result is not None
        assert result["total_return_pct"] < 0
        dates = pd.bdate_range(start="2023-01-03", end="2023-12-15")
        prices = np.linspace(start_price, end_price, len(dates))
        expected = round((prices[-1] - prices[0]) / prices[0] * 100, 4)
        assert result["total_return_pct"] == expected


class TestCompareUserReturnToBenchmarks:
    @patch(_MOCK_YF)
    def test_returns_expected_structure(self, mock_dl):
        mock_dl.return_value = _make_df("2023-01-03", "2023-12-15", 400.0, 480.0)
        result = compare_user_return_to_benchmarks(
            _sample_trades(), after_cost_return_pct=25.0
        )
        assert "after_cost_return_pct" in result
        assert "comparisons" in result
        assert "best_alpha_ticker" in result
        assert "any_benchmark_available" in result

    @patch(_MOCK_YF)
    def test_alpha_is_correct(self, mock_dl):
        # Benchmark returns 20%, user returns 25% -> alpha = 5%
        mock_dl.return_value = _make_df("2023-01-03", "2023-12-15", 400.0, 480.0)
        result = compare_user_return_to_benchmarks(
            _sample_trades(), after_cost_return_pct=25.0, tickers=["SPY"]
        )
        spy = result["comparisons"][0]
        assert spy["ticker"] == "SPY"
        assert spy["available"] is True
        expected_alpha = round(25.0 - spy["benchmark_return_pct"], 4)
        assert spy["alpha_pct"] == expected_alpha

    @patch(_MOCK_YF)
    def test_outperformed_flag_true_when_alpha_positive(self, mock_dl):
        mock_dl.return_value = _make_df("2023-01-03", "2023-12-15", 400.0, 440.0)
        result = compare_user_return_to_benchmarks(
            _sample_trades(), after_cost_return_pct=20.0, tickers=["SPY"]
        )
        spy = result["comparisons"][0]
        assert spy["outperformed"] is True

    @patch(_MOCK_YF)
    def test_outperformed_flag_false_when_alpha_negative(self, mock_dl):
        mock_dl.return_value = _make_df("2023-01-03", "2023-12-15", 400.0, 480.0)
        result = compare_user_return_to_benchmarks(
            _sample_trades(), after_cost_return_pct=5.0, tickers=["QQQ"]
        )
        qqq = result["comparisons"][0]
        assert qqq["outperformed"] is False

    @patch(_MOCK_YF)
    def test_defaults_to_spy_and_qqq(self, mock_dl):
        mock_dl.return_value = _make_df("2023-01-03", "2023-12-15", 400.0, 480.0)
        result = compare_user_return_to_benchmarks(
            _sample_trades(), after_cost_return_pct=10.0
        )
        tickers_returned = [c["ticker"] for c in result["comparisons"]]
        assert "SPY" in tickers_returned
        assert "QQQ" in tickers_returned

    @patch(_MOCK_YF)
    def test_benchmark_unavailable_marked_correctly(self, mock_dl):
        mock_dl.return_value = pd.DataFrame()  # empty -> fetch_benchmark returns None
        result = compare_user_return_to_benchmarks(
            _sample_trades(), after_cost_return_pct=10.0, tickers=["SPY"]
        )
        spy = result["comparisons"][0]
        assert spy["available"] is False
        assert spy["benchmark_return_pct"] is None
        assert spy["alpha_pct"] is None
        assert result["any_benchmark_available"] is False
        assert result["best_alpha_ticker"] is None

    def test_empty_trades_returns_unavailable(self):
        result = compare_user_return_to_benchmarks(
            [], after_cost_return_pct=10.0, tickers=["SPY"]
        )
        assert result["any_benchmark_available"] is False
        assert result["comparisons"][0]["available"] is False

    @patch(_MOCK_YF)
    def test_best_alpha_ticker_is_highest_alpha(self, mock_dl):
        # SPY call returns higher benchmark (smaller alpha), QQQ returns lower (larger alpha)
        def _side_effect(ticker, **kwargs):
            if ticker == "SPY":
                return _make_df("2023-01-03", "2023-12-15", 400.0, 480.0)  # ~20% return
            return _make_df("2023-01-03", "2023-12-15", 400.0, 420.0)  # ~5% return

        mock_dl.side_effect = _side_effect
        result = compare_user_return_to_benchmarks(
            _sample_trades(), after_cost_return_pct=15.0
        )
        # User 15% vs SPY ~20% (alpha=-5), vs QQQ ~5% (alpha=+10) -> QQQ is best
        assert result["best_alpha_ticker"] == "QQQ"

    @patch(_MOCK_YF)
    def test_after_cost_return_pct_preserved_in_output(self, mock_dl):
        mock_dl.return_value = _make_df("2023-01-03", "2023-12-15", 400.0, 480.0)
        result = compare_user_return_to_benchmarks(
            _sample_trades(), after_cost_return_pct=12.3456, tickers=["SPY"]
        )
        assert result["after_cost_return_pct"] == round(12.3456, 4)

    @pytest.mark.parametrize("bad_val", [None, "15.0", float("nan")])
    def test_invalid_after_cost_return_pct_raises(self, bad_val):
        with pytest.raises((ValueError, TypeError)):
            compare_user_return_to_benchmarks(
                _sample_trades(), after_cost_return_pct=bad_val, tickers=["SPY"]
            )

    @patch(_MOCK_YF)
    def test_exact_tie_is_not_outperformed(self, mock_dl):
        # Make benchmark return exactly match the user return so alpha == 0
        mock_dl.return_value = _make_df("2023-01-03", "2023-12-15", 400.0, 480.0)
        spy_benchmark = fetch_benchmark(_sample_trades(), "SPY")
        mock_dl.return_value = _make_df("2023-01-03", "2023-12-15", 400.0, 480.0)
        result = compare_user_return_to_benchmarks(
            _sample_trades(),
            after_cost_return_pct=spy_benchmark["total_return_pct"],
            tickers=["SPY"],
        )
        spy = result["comparisons"][0]
        assert spy["alpha_pct"] == 0.0
        assert spy["outperformed"] is False

    @patch(_MOCK_YF)
    def test_all_benchmarks_unavailable(self, mock_dl):
        mock_dl.return_value = pd.DataFrame()  # all fetches fail
        result = compare_user_return_to_benchmarks(
            _sample_trades(), after_cost_return_pct=10.0, tickers=["SPY", "QQQ"]
        )
        assert result["any_benchmark_available"] is False
        assert result["best_alpha_ticker"] is None
        assert all(not c["available"] for c in result["comparisons"])

    @patch(_MOCK_YF)
    def test_verdict_included_in_result(self, mock_dl):
        mock_dl.return_value = _make_df("2023-01-03", "2023-12-15", 400.0, 480.0)
        result = compare_user_return_to_benchmarks(
            _sample_trades(), after_cost_return_pct=25.0
        )
        assert "verdict" in result
        assert isinstance(result["verdict"], str)
        assert len(result["verdict"]) > 0


class TestGenerateVerdict:
    def _make_result(self, user_return, comparisons, any_available=True):
        return {
            "after_cost_return_pct": user_return,
            "comparisons": comparisons,
            "any_benchmark_available": any_available,
        }

    def test_no_benchmark_available(self):
        result = self._make_result(10.0, [], any_available=False)
        assert (
            generate_verdict(result)
            == "No benchmark data available to compare your results."
        )

    def test_underperformed_all(self):
        result = self._make_result(
            5.0,
            [
                {
                    "ticker": "SPY",
                    "benchmark_return_pct": 20.0,
                    "alpha_pct": -15.0,
                    "outperformed": False,
                    "available": True,
                },
            ],
        )
        verdict = generate_verdict(result)
        assert "SPY" in verdict
        assert "15.0%" in verdict
        assert "Buying and holding" in verdict

    def test_beat_all(self):
        result = self._make_result(
            30.0,
            [
                {
                    "ticker": "SPY",
                    "benchmark_return_pct": 20.0,
                    "alpha_pct": 10.0,
                    "outperformed": True,
                    "available": True,
                },
                {
                    "ticker": "QQQ",
                    "benchmark_return_pct": 25.0,
                    "alpha_pct": 5.0,
                    "outperformed": True,
                    "available": True,
                },
            ],
        )
        verdict = generate_verdict(result)
        assert "beat every benchmark" in verdict
        assert "30.0%" in verdict

    def test_beat_all_single_benchmark(self):
        result = self._make_result(
            30.0,
            [
                {
                    "ticker": "SPY",
                    "benchmark_return_pct": 20.0,
                    "alpha_pct": 10.0,
                    "outperformed": True,
                    "available": True,
                },
            ],
        )
        verdict = generate_verdict(result)
        assert "beat every benchmark" in verdict
        assert "SPY" in verdict
        assert "20.0%" in verdict

    def test_mixed_results(self):
        result = self._make_result(
            15.0,
            [
                {
                    "ticker": "SPY",
                    "benchmark_return_pct": 10.0,
                    "alpha_pct": 5.0,
                    "outperformed": True,
                    "available": True,
                },
                {
                    "ticker": "QQQ",
                    "benchmark_return_pct": 25.0,
                    "alpha_pct": -10.0,
                    "outperformed": False,
                    "available": True,
                },
            ],
        )
        verdict = generate_verdict(result)
        assert "SPY" in verdict
        assert "QQQ" in verdict
        # gap should be for QQQ (the only underperformer), matching the named ticker
        assert "10.0%" in verdict

    def test_mixed_results_gap_matches_named_ticker(self):
        # When underperforming two benchmarks, only the worst is named and its gap is shown
        result = self._make_result(
            10.0,
            [
                {
                    "ticker": "SPY",
                    "benchmark_return_pct": 12.0,
                    "alpha_pct": -2.0,
                    "outperformed": False,
                    "available": True,
                },
                {
                    "ticker": "QQQ",
                    "benchmark_return_pct": 20.0,
                    "alpha_pct": -10.0,
                    "outperformed": False,
                    "available": True,
                },
                {
                    "ticker": "DIA",
                    "benchmark_return_pct": 8.0,
                    "alpha_pct": 2.0,
                    "outperformed": True,
                    "available": True,
                },
            ],
        )
        verdict = generate_verdict(result)
        # DIA was beaten, QQQ is the worst underperformer
        assert "DIA" in verdict
        assert "QQQ" in verdict
        assert "10.0%" in verdict
        # SPY should not be named — only the worst underperformer is
        assert "SPY" not in verdict

    def test_unavailable_benchmarks_ignored_in_verdict(self):
        result = self._make_result(
            10.0,
            [
                {
                    "ticker": "SPY",
                    "benchmark_return_pct": None,
                    "alpha_pct": None,
                    "outperformed": False,
                    "available": False,
                },
            ],
            any_available=False,
        )
        verdict = generate_verdict(result)
        assert verdict == "No benchmark data available to compare your results."
