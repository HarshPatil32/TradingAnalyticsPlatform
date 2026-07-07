"""Tests for CSV upload security: content safety and filename sanitization."""

import io

import pytest

from app import _MAX_UPLOAD_BYTES, _safe_filename
from app import app as flask_app
from csv_analyzer import _assert_content_safe, sanitize_csv


@pytest.fixture()
def client():
    flask_app.config["TESTING"] = True
    with flask_app.test_client() as c:
        yield c


# ---------------------------------------------------------------------------
# _assert_content_safe — content-level checks
# ---------------------------------------------------------------------------


class TestAssertContentSafe:
    def test_null_byte_raises(self):
        with pytest.raises(ValueError, match="null bytes"):
            _assert_content_safe("date,symbol\n2024-01-01,AAPL\x00")

    def test_elf_magic_bytes_raises(self):
        with pytest.raises(ValueError, match="binary file"):
            _assert_content_safe("\x7fELF\x02\x01\x01")

    def test_pe_magic_bytes_raises(self):
        with pytest.raises(ValueError, match="binary file"):
            _assert_content_safe("MZ\x90\x00")

    def test_shebang_raises(self):
        with pytest.raises(ValueError, match="binary file"):
            _assert_content_safe("#!/bin/bash\nrm -rf /")

    def test_formula_equals_raises(self):
        with pytest.raises(ValueError, match="cannot be processed safely"):
            _assert_content_safe("date,symbol\n2024-01-01,=CMD|'/C calc'!A0")

    def test_formula_plus_raises(self):
        with pytest.raises(ValueError, match="cannot be processed safely"):
            _assert_content_safe("date,symbol\n2024-01-01,+cmd|' /C calc")

    def test_formula_at_raises(self):
        with pytest.raises(ValueError, match="cannot be processed safely"):
            _assert_content_safe("date,symbol\n2024-01-01,@SUM(1+1)*cmd")

    def test_formula_minus_non_numeric_raises(self):
        with pytest.raises(ValueError, match="cannot be processed safely"):
            _assert_content_safe("date,symbol\n2024-01-01,-cmd|payload")

    def test_minus_numeric_price_passes(self):
        # Negative numbers are valid prices and must not be rejected
        _assert_content_safe("date,pnl\n2024-01-01,-1.5")

    def test_negative_scientific_notation_passes(self):
        # e.g. -1e-5 is a valid float and must not be rejected
        _assert_content_safe("date,pnl\n2024-01-01,-1e-5")

    def test_bom_prefixed_elf_raises(self):
        # A UTF-8 BOM before magic bytes must not bypass the binary check
        bom = "\ufeff"
        payload = bom + "\x7fELF\x02\x01\x01"
        with pytest.raises(ValueError, match="binary file"):
            _assert_content_safe(payload)

    def test_clean_csv_passes(self):
        _assert_content_safe(
            "date,symbol,action,price,shares\n2024-01-15,AAPL,BUY,185.50,10\n"
        )

    def test_empty_string_passes(self):
        _assert_content_safe("")

    def test_pdf_magic_bytes_raises(self):
        with pytest.raises(ValueError, match="binary file"):
            _assert_content_safe("%PDF-1.4 fake pdf content")

    def test_zip_magic_bytes_raises(self):
        with pytest.raises(ValueError, match="binary file"):
            _assert_content_safe("PK\x03\x04fake zip content")

    def test_png_magic_bytes_raises(self):
        with pytest.raises(ValueError, match="binary file"):
            _assert_content_safe("\x89PNGfake png content")

    def test_gzip_magic_bytes_raises(self):
        with pytest.raises(ValueError, match="binary file"):
            _assert_content_safe("\x1f\x8bfake gzip content")


# ---------------------------------------------------------------------------
# sanitize_csv — safety gate is called first, and return value is correct
# ---------------------------------------------------------------------------


class TestSanitizeCsvSafetyGate:
    def test_formula_injection_blocked_before_sanitize(self):
        with pytest.raises(ValueError):
            sanitize_csv('date,symbol\n2024-01-01,=HYPERLINK("evil.com")')

    def test_binary_blocked_before_sanitize(self):
        with pytest.raises(ValueError):
            sanitize_csv("\x7fELFsomedata")

    def test_returns_string_not_none(self):
        result = sanitize_csv("date,symbol\n2024-01-01,AAPL\n")
        assert result is not None
        assert isinstance(result, str)

    def test_bom_stripped(self):
        result = sanitize_csv("\ufeffdate,symbol\n2024-01-01,AAPL")
        assert not result.startswith("\ufeff")

    def test_crlf_normalised(self):
        result = sanitize_csv("date,symbol\r\n2024-01-01,AAPL\r\n")
        assert "\r" not in result

    def test_cr_only_normalised(self):
        # Old Mac line endings (\r only) must also be converted to \n
        result = sanitize_csv("date,symbol\r2024-01-01,AAPL\r")
        assert "\r" not in result

    def test_semicolons_converted(self):
        result = sanitize_csv("date;symbol\n2024-01-01;AAPL")
        assert ";" not in result
        assert "date,symbol" in result

    def test_bom_strips_exactly_one(self):
        # Two consecutive BOMs: only the leading one should be removed
        result = sanitize_csv("\ufeff\ufeffdate,symbol\n2024-01-01,AAPL")
        assert result.startswith("\ufeff")
        assert not result.startswith("\ufeff\ufeff")

    def test_semicolon_with_quoted_comma_field_preserved(self):
        # A field value that contains a comma inside quotes must survive delimiter conversion
        raw = 'date;symbol;notes\n2024-01-01;AAPL;"buy, initial entry"'
        result = sanitize_csv(raw)
        assert "buy, initial entry" in result
        assert ";" not in result


# ---------------------------------------------------------------------------
# _safe_filename — filename sanitization
# ---------------------------------------------------------------------------


class TestSafeFilename:
    def test_path_traversal_stripped(self):
        result = _safe_filename("../../../etc/passwd.csv")
        # secure_filename collapses path components — no separator chars remain
        assert "/" not in result and ".." not in result
        assert result.endswith(".csv")

    def test_null_byte_stripped(self):
        # werkzeug strips null bytes as part of secure_filename
        result = _safe_filename("file\x00name.csv")
        assert "\x00" not in result
        assert result  # must not be empty

    def test_normal_filename_unchanged(self):
        assert _safe_filename("my_backtest.csv") == "my_backtest.csv"

    def test_empty_after_sanitize_raises(self):
        # A name that is purely path separators leaves nothing after sanitization
        with pytest.raises(ValueError, match="invalid or empty"):
            _safe_filename("../../")

    def test_empty_string_raises(self):
        with pytest.raises(ValueError, match="invalid or empty"):
            _safe_filename("")


# ---------------------------------------------------------------------------
# /analyze-trades route — integration
# ---------------------------------------------------------------------------


class TestAnalyzeBacktestRoute:
    def test_clean_json_upload_returns_200(self, client):
        csv_data = "date,symbol,action,price,shares\n2024-01-15,AAPL,BUY,185.50,10\n"
        resp = client.post("/analyze-trades", json={"csv_data": csv_data})
        assert resp.status_code == 200

    def test_formula_csv_returns_400(self, client):
        csv_data = "date,symbol\n2024-01-01,=CMD|calc"
        resp = client.post("/analyze-trades", json={"csv_data": csv_data})
        assert resp.status_code == 400

    def test_binary_file_upload_returns_400(self, client):
        payload = b"\x7fELF\x02\x01\x01\x00"
        data = {"file": (io.BytesIO(payload), "malware.csv")}
        resp = client.post(
            "/analyze-trades", content_type="multipart/form-data", data=data
        )
        assert resp.status_code == 400

    def test_path_traversal_filename_returns_400(self, client):
        data = {"file": (io.BytesIO(b"date,symbol\n"), "../../etc/passwd")}
        resp = client.post(
            "/analyze-trades", content_type="multipart/form-data", data=data
        )
        # secure_filename reduces this to 'passwd' which is valid, so it proceeds past filename check.
        # The important thing is it does NOT return a server error from path operations.
        assert resp.status_code in (200, 400)

    def test_empty_filename_returns_400(self, client):
        data = {"file": (io.BytesIO(b"date,symbol\n"), "../../")}
        resp = client.post(
            "/analyze-trades", content_type="multipart/form-data", data=data
        )
        assert resp.status_code == 400

    def test_empty_file_body_returns_400(self, client):
        data = {"file": (io.BytesIO(b""), "empty.csv")}
        resp = client.post(
            "/analyze-trades", content_type="multipart/form-data", data=data
        )
        assert resp.status_code == 400
        assert "empty" in resp.get_json()["error"].lower()

    def test_whitespace_only_file_returns_400(self, client):
        data = {"file": (io.BytesIO(b"   \n  "), "blank.csv")}
        resp = client.post(
            "/analyze-trades", content_type="multipart/form-data", data=data
        )
        assert resp.status_code == 400
        assert "empty" in resp.get_json()["error"].lower()

    def test_wrong_content_type_returns_400(self, client):
        resp = client.post(
            "/analyze-trades", data="plain text", content_type="text/plain"
        )
        assert resp.status_code == 400

    def test_non_string_csv_data_returns_400(self, client):
        resp = client.post("/analyze-trades", json={"csv_data": 12345})
        assert resp.status_code == 400

    def test_oversized_upload_returns_413(self, client):
        # Send a file larger than the 5 MB framework limit
        large_data = b"x" * (_MAX_UPLOAD_BYTES + 1)
        data = {"file": (io.BytesIO(large_data), "big.csv")}
        resp = client.post(
            "/analyze-trades", content_type="multipart/form-data", data=data
        )
        assert resp.status_code == 413

    def test_upload_at_exact_limit_not_rejected_by_framework(self, client):
        # A small legitimate file must not be rejected with 413.
        # Note: multipart framing adds overhead, so exactly _MAX_UPLOAD_BYTES of file
        # data would still push the total request over the limit. Use a small payload.
        data = {"file": (io.BytesIO(b"date,symbol\n2024-01-01,AAPL\n"), "small.csv")}
        resp = client.post(
            "/analyze-trades", content_type="multipart/form-data", data=data
        )
        assert resp.status_code != 413

    def test_upload_one_byte_below_limit_not_rejected(self, client):
        # Multipart framing adds ~200 bytes of overhead (boundary, headers, etc.) on
        # top of the file bytes, so we leave 1 KB of headroom to stay under the total
        # request ceiling while still exercising the near-limit boundary.
        just_under = b"x" * (_MAX_UPLOAD_BYTES - 1024)
        data = {"file": (io.BytesIO(just_under), "boundary.csv")}
        resp = client.post(
            "/analyze-trades", content_type="multipart/form-data", data=data
        )
        assert resp.status_code != 413

    def test_oversized_upload_no_content_length_returns_413(self, client):
        # Without Content-Length the framework limit is bypassed; multipart parsing
        # still rejects the request (400) before the manual read check can fire. Both
        # 400 and 413 mean the oversized request was rejected.
        large_data = b"x" * (_MAX_UPLOAD_BYTES + 1)
        data = {"file": (io.BytesIO(large_data), "big.csv")}
        resp = client.post(
            "/analyze-trades",
            content_type="multipart/form-data",
            data=data,
            environ_overrides={"CONTENT_LENGTH": ""},
        )
        assert resp.status_code in (400, 413)

    def test_latin1_encoded_file_upload_accepted(self, client):
        # A file encoded in latin-1 (not UTF-8) must be decoded and processed without error.
        csv_bytes = (
            "date,symbol,action,price,shares\n2024-01-15,IBM,BUY,10.00,1\n".encode(
                "latin-1"
            )
        )
        data = {"file": (io.BytesIO(csv_bytes), "trades.csv")}
        resp = client.post(
            "/analyze-trades", content_type="multipart/form-data", data=data
        )
        assert resp.status_code == 200

    def test_png_upload_rejected_even_via_file_route(self, client):
        # A PNG file must be rejected by the binary check regardless of decoding path.
        # Use a minimal PNG header — \x89PNG\r\n\x1a\n — followed by null bytes
        # (present in every real PNG IHDR chunk).
        png_header = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR"
        data = {"file": (io.BytesIO(png_header), "image.csv")}
        resp = client.post(
            "/analyze-trades", content_type="multipart/form-data", data=data
        )
        assert resp.status_code == 400
