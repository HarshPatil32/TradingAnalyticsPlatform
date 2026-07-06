"""Tests for per-IP monthly rate limiting on /analyze-trades."""

from unittest.mock import patch

import pytest

from app import MONTHLY_ANALYSIS_LIMIT, app

VALID_CSV = "Date,Symbol,Action,Quantity,Price\n2024-01-10,AAPL,BUY,10,150.00\n2024-01-20,AAPL,SELL,10,160.00\n"
TEST_IP = "1.2.3.4"
FIXED_MONTH = "2099-01"


@pytest.fixture()
def client():
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


def _post_analysis(client, ip=TEST_IP, month=FIXED_MONTH):
    with (
        patch("app._get_client_ip", return_value=ip),
        patch("app._get_month_key", return_value=month),
    ):
        return client.post(
            "/analyze-trades",
            data={"file": (VALID_CSV.encode(), "trades.csv")},
            content_type="multipart/form-data",
        )


class TestRateLimiting:
    def test_first_request_allowed(self, client):
        resp = _post_analysis(client)
        assert resp.status_code != 429

    def test_requests_up_to_limit_allowed(self, client):
        for i in range(MONTHLY_ANALYSIS_LIMIT):
            resp = _post_analysis(client)
            assert resp.status_code != 429, f"Request {i + 1} should be allowed"

    def test_request_over_limit_rejected(self, client):
        for _ in range(MONTHLY_ANALYSIS_LIMIT):
            _post_analysis(client)
        resp = _post_analysis(client)
        assert resp.status_code == 429

    def test_rate_limit_error_message(self, client):
        for _ in range(MONTHLY_ANALYSIS_LIMIT):
            _post_analysis(client)
        resp = _post_analysis(client)
        data = resp.get_json()
        assert "error" in data
        assert str(MONTHLY_ANALYSIS_LIMIT) in data["error"]
        assert "per month" in data["error"]
        assert "1st of next month" in data["error"]

    def test_different_ips_have_separate_limits(self, client):
        # Exhaust ip_a
        for _ in range(MONTHLY_ANALYSIS_LIMIT):
            _post_analysis(client, ip="1.1.1.1")

        # ip_b should still be allowed
        resp = _post_analysis(client, ip="2.2.2.2")
        assert resp.status_code != 429

    def test_new_month_resets_limit(self, client):
        # Exhaust limit in month 1
        for _ in range(MONTHLY_ANALYSIS_LIMIT):
            _post_analysis(client, month="2099-01")

        # Month 2 should be allowed for the same IP
        resp = _post_analysis(client, month="2099-02")
        assert resp.status_code != 429
