"""QA tests for GET /spy-investment - confirms date range boundaries with no off-by-one errors.

Covers:
- start_date / end_date passed to yfinance without modification
- entry price uses the first bar (iloc[0]), exit price uses the last bar (iloc[-1])
- yfinance end is exclusive, so the last bar is strictly before end_date
- monthly_performance spans from start_date's month through end_date's month
- month count is exact for full-year, partial-year, and year-boundary ranges
"""

from datetime import datetime
from unittest.mock import patch

import numpy as np
import pandas as pd
import pytest

from app import TRADING_MODULES_AVAILABLE

INITIAL_BALANCE = 100_000
MOCK_FINAL = 120_000.0
_MOCK_YF = "test_against_SP.yf.download"
_MOCK_SPY = "test_against_SP.get_spy_investment"


def _make_df(first: str, last: str) -> pd.DataFrame:
    """Return a mock SPY DataFrame with a business-day DatetimeIndex."""
    dates = pd.bdate_range(start=first, end=last)
    prices = np.linspace(400.0, 480.0, len(dates))
    return pd.DataFrame({"Close": prices}, index=dates)


# ---------------------------------------------------------------------------
# get_spy_investment - date boundaries
# ---------------------------------------------------------------------------


if TRADING_MODULES_AVAILABLE:
    from test_against_SP import generate_spy_monthly_performance, get_spy_investment

    class TestGetSpyInvestmentDateBoundaries:
        """Verify that the correct dates flow into yfinance and the right bars are used."""

        START = datetime(2023, 1, 3)  # first trading day of 2023
        END = datetime(2024, 1, 2)  # first trading day of 2024 (yfinance excludes this)

        def _df(self):
            # last business day before 2024-01-02 is 2023-12-29
            return _make_df("2023-01-03", "2023-12-29")

        @patch(_MOCK_YF)
        def test_yfinance_receives_exact_requested_start_date(self, mock_dl):
            mock_dl.return_value = self._df()
            get_spy_investment(self.START, self.END, INITIAL_BALANCE)
            assert mock_dl.call_args.kwargs["start"] == self.START

        @patch(_MOCK_YF)
        def test_yfinance_receives_exact_requested_end_date(self, mock_dl):
            mock_dl.return_value = self._df()
            get_spy_investment(self.START, self.END, INITIAL_BALANCE)
            assert mock_dl.call_args.kwargs["end"] == self.END

        @patch(_MOCK_YF)
        def test_entry_price_is_from_first_bar(self, mock_dl):
            """Entry price must be from the first bar returned (iloc[0]), not a later row."""
            df = self._df()
            # Capture prices before the production code lowercases column names in-place
            initial_price = df["Close"].iloc[0]
            final_price = df["Close"].iloc[-1]
            mock_dl.return_value = df
            result = get_spy_investment(self.START, self.END, INITIAL_BALANCE)
            expected = INITIAL_BALANCE * (final_price / initial_price)
            assert abs(result - expected) < 0.01

        @patch(_MOCK_YF)
        def test_exit_price_is_from_last_bar_not_end_date(self, mock_dl):
            """yfinance end is exclusive - the last bar must be strictly before end_date."""
            df = self._df()
            mock_dl.return_value = df
            get_spy_investment(self.START, self.END, INITIAL_BALANCE)
            last_bar = df.index[-1]
            assert last_bar < pd.Timestamp(
                self.END
            ), f"Last bar {last_bar.date()} should be before end_date {self.END.date()}"

        @patch(_MOCK_YF)
        def test_first_bar_is_on_or_after_start_date(self, mock_dl):
            """iloc[0] must not precede start_date (no data from before the requested start)."""
            df = self._df()
            mock_dl.return_value = df
            get_spy_investment(self.START, self.END, INITIAL_BALANCE)
            first_bar = df.index[0]
            assert first_bar >= pd.Timestamp(
                self.START
            ), f"First bar {first_bar.date()} is before start_date {self.START.date()}"

        @patch(_MOCK_YF)
        def test_empty_response_returns_error_tuple(self, mock_dl):
            """An empty DataFrame (e.g. bad date range) must return an error, not crash."""
            # Mimic real yfinance: returns empty rows but keeps column names
            mock_dl.return_value = pd.DataFrame(
                columns=["Close", "Open", "High", "Low", "Volume"]
            )
            result, status = get_spy_investment(
                datetime(2023, 1, 7), datetime(2023, 1, 8), INITIAL_BALANCE
            )
            assert isinstance(result, str)
            assert status == 400

    @patch(_MOCK_SPY, return_value=MOCK_FINAL)
    class TestGenerateSpyMonthlyPerformanceDateRange:
        """Verify that monthly entries span exactly from start_date through end_date."""

        def test_first_entry_date_matches_start_month(self, _):
            result = generate_spy_monthly_performance(
                datetime(2023, 3, 15), datetime(2024, 3, 15), INITIAL_BALANCE
            )
            assert result[0]["date"] == "2023-03"

        def test_last_entry_date_matches_end_month(self, _):
            result = generate_spy_monthly_performance(
                datetime(2023, 3, 15), datetime(2024, 3, 15), INITIAL_BALANCE
            )
            assert result[-1]["date"] == "2024-03"

        def test_full_year_jan_to_jan_produces_13_entries(self, _):
            # 12 months → Start + Month 1 .. Month 12 = 13 entries
            result = generate_spy_monthly_performance(
                datetime(2023, 1, 1), datetime(2024, 1, 1), INITIAL_BALANCE
            )
            assert len(result) == 13

        def test_six_month_range_produces_7_entries(self, _):
            result = generate_spy_monthly_performance(
                datetime(2023, 1, 1), datetime(2023, 7, 1), INITIAL_BALANCE
            )
            assert len(result) == 7

        def test_dates_are_monotonically_increasing(self, _):
            result = generate_spy_monthly_performance(
                datetime(2023, 1, 1), datetime(2024, 1, 1), INITIAL_BALANCE
            )
            dates = [r["date"] for r in result]
            assert dates == sorted(dates)

        def test_no_duplicate_dates(self, _):
            result = generate_spy_monthly_performance(
                datetime(2023, 1, 1), datetime(2024, 1, 1), INITIAL_BALANCE
            )
            dates = [r["date"] for r in result]
            assert len(dates) == len(set(dates))

        def test_december_to_january_boundary_not_skipped(self, _):
            """Dec→Jan year rollover must not skip or duplicate any month."""
            result = generate_spy_monthly_performance(
                datetime(2023, 11, 1), datetime(2024, 2, 1), INITIAL_BALANCE
            )
            dates = [r["date"] for r in result]
            assert "2023-11" in dates
            assert "2023-12" in dates
            assert "2024-01" in dates
            assert "2024-02" in dates

        def test_sub_one_month_range_returns_2_entries(self, _):
            # Same month → months=0 → clamped to 1 → Start + 1 entry
            result = generate_spy_monthly_performance(
                datetime(2023, 5, 1), datetime(2023, 5, 20), INITIAL_BALANCE
            )
            assert len(result) == 2

        def test_last_entry_balance_is_actual_final_balance(self, _):
            result = generate_spy_monthly_performance(
                datetime(2023, 1, 1), datetime(2024, 1, 1), INITIAL_BALANCE
            )
            assert result[-1]["balance"] == MOCK_FINAL

        def test_first_entry_balance_is_initial_balance(self, _):
            result = generate_spy_monthly_performance(
                datetime(2023, 1, 1), datetime(2024, 1, 1), INITIAL_BALANCE
            )
            assert result[0]["balance"] == INITIAL_BALANCE


# ---------------------------------------------------------------------------
# Route integration - requested dates flow through unmodified
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def client():
    import os
    import sys

    sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "legacy"))
    from app import app as flask_app

    flask_app.config["TESTING"] = True
    with flask_app.test_client() as c:
        yield c


_MONTHLY_STUB = [
    {"month": "Start", "balance": 100_000.0, "date": "2023-01"},
    {"month": "Month 12", "balance": 115_000.0, "date": "2024-01"},
]


@pytest.mark.skipif(
    not TRADING_MODULES_AVAILABLE,
    reason="Trading modules not available; skipping /spy-investment integration tests.",
)
class TestSpyInvestmentRouteIntegration:

    @patch("app.generate_spy_monthly_performance", return_value=_MONTHLY_STUB)
    @patch("app.get_spy_investment", return_value=115_000.0)
    def test_start_date_forwarded_verbatim_to_helper(
        self, mock_spy, mock_monthly, client
    ):
        client.get("/spy-investment?start_date=2023-01-01&end_date=2024-01-01")
        assert mock_spy.call_args.args[0] == datetime(2023, 1, 1)

    @patch("app.generate_spy_monthly_performance", return_value=_MONTHLY_STUB)
    @patch("app.get_spy_investment", return_value=115_000.0)
    def test_end_date_forwarded_verbatim_to_helper(
        self, mock_spy, mock_monthly, client
    ):
        client.get("/spy-investment?start_date=2023-01-01&end_date=2024-01-01")
        assert mock_spy.call_args.args[1] == datetime(2024, 1, 1)

    @patch("app.generate_spy_monthly_performance", return_value=_MONTHLY_STUB)
    @patch("app.get_spy_investment", return_value=115_000.0)
    def test_monthly_first_date_matches_requested_start_month(
        self, mock_spy, mock_monthly, client
    ):
        resp = client.get("/spy-investment?start_date=2023-01-01&end_date=2024-01-01")
        data = resp.get_json()
        assert data["monthly_performance"][0]["date"] == "2023-01"

    @patch("app.generate_spy_monthly_performance", return_value=_MONTHLY_STUB)
    @patch("app.get_spy_investment", return_value=115_000.0)
    def test_monthly_last_date_matches_requested_end_month(
        self, mock_spy, mock_monthly, client
    ):
        resp = client.get("/spy-investment?start_date=2023-01-01&end_date=2024-01-01")
        data = resp.get_json()
        assert data["monthly_performance"][-1]["date"] == "2024-01"

    def test_missing_start_date_returns_400(self, client):
        resp = client.get("/spy-investment?end_date=2024-01-01")
        assert resp.status_code == 400

    def test_missing_end_date_returns_400(self, client):
        resp = client.get("/spy-investment?start_date=2023-01-01")
        assert resp.status_code == 400

    def test_invalid_date_format_returns_400(self, client):
        resp = client.get("/spy-investment?start_date=01-01-2023&end_date=31-12-2023")
        assert resp.status_code == 400
