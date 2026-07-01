"""Tests that security headers are present on every Flask response."""
import pytest
from app import app, CSP_POLICY, SECURITY_HEADERS


@pytest.fixture()
def client():
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


def _assert_headers_on_response(resp):
    assert resp.headers["Content-Security-Policy"] == CSP_POLICY
    for name, value in SECURITY_HEADERS.items():
        assert resp.headers[name] == value


class TestCSPHeader:
    def test_present_on_root(self, client):
        resp = client.get("/")
        assert "Content-Security-Policy" in resp.headers

    def test_present_on_heartbeat(self, client):
        resp = client.get("/heartbeat")
        assert "Content-Security-Policy" in resp.headers

    def test_present_on_404(self, client):
        resp = client.get("/nonexistent-route-xyz")
        assert "Content-Security-Policy" in resp.headers

    def test_value_matches_policy_constant(self, client):
        resp = client.get("/heartbeat")
        assert resp.headers["Content-Security-Policy"] == CSP_POLICY

    def test_default_src_none(self, client):
        resp = client.get("/")
        assert "default-src 'none'" in resp.headers["Content-Security-Policy"]

    def test_frame_ancestors_none(self, client):
        resp = client.get("/")
        assert "frame-ancestors 'none'" in resp.headers["Content-Security-Policy"]

    def test_base_uri_self(self, client):
        resp = client.get("/")
        assert "base-uri 'self'" in resp.headers["Content-Security-Policy"]

    def test_csp_present_on_options_preflight(self, client):
        resp = client.options("/heartbeat")
        assert "Content-Security-Policy" in resp.headers


class TestStandardSecurityHeaders:
    @pytest.mark.parametrize("path", ["/", "/heartbeat", "/nonexistent-route-xyz"])
    def test_present_on_responses(self, client, path):
        resp = client.get(path)
        _assert_headers_on_response(resp)

    def test_present_on_options_preflight(self, client):
        resp = client.options("/heartbeat")
        _assert_headers_on_response(resp)

    @pytest.mark.parametrize("header_name", list(SECURITY_HEADERS.keys()))
    def test_values_match_constants(self, client, header_name):
        resp = client.get("/heartbeat")
        assert resp.headers[header_name] == SECURITY_HEADERS[header_name]
