"""Unit tests for request guard scenarios."""
from __future__ import annotations

import pytest

from safe_fetch._exceptions import (
    InvalidSchemeError,
    PIILeakError,
    Policy,
    SSRFBlockedError,
    SecretLeakError,
)
from safe_fetch._request_guard import (
    _luhn_valid,
    _scan_value_for_pii,
    _scan_value_for_secrets,
    check_ssrf,
    scan_request,
    validate_url_scheme,
)


# ---------------------------------------------------------------------------
# Scheme validation
# ---------------------------------------------------------------------------

class TestSchemeValidation:
    def test_https_allowed(self):
        validate_url_scheme("https://example.com/page")

    def test_http_allowed(self):
        validate_url_scheme("http://example.com/page")

    def test_file_scheme_rejected(self):
        with pytest.raises(InvalidSchemeError):
            validate_url_scheme("file:///etc/passwd")

    def test_ftp_scheme_rejected(self):
        with pytest.raises(InvalidSchemeError):
            validate_url_scheme("ftp://example.com/file")

    def test_data_scheme_rejected(self):
        with pytest.raises(InvalidSchemeError):
            validate_url_scheme("data:text/html,<h1>test</h1>")


# ---------------------------------------------------------------------------
# SSRF / private IP blocking
# ---------------------------------------------------------------------------

class TestSSRF:
    def test_private_ip_192_blocked(self):
        with pytest.raises(SSRFBlockedError):
            check_ssrf("http://192.168.1.1/admin")

    def test_private_ip_10_blocked(self):
        with pytest.raises(SSRFBlockedError):
            check_ssrf("http://10.0.0.1/")

    def test_loopback_blocked(self):
        with pytest.raises(SSRFBlockedError):
            check_ssrf("http://127.0.0.1/")

    def test_aws_metadata_blocked(self):
        with pytest.raises(SSRFBlockedError):
            check_ssrf("http://169.254.169.254/latest/meta-data/")

    def test_ipv6_loopback_blocked(self):
        with pytest.raises(SSRFBlockedError):
            check_ssrf("http://[::1]/")


# ---------------------------------------------------------------------------
# PII detection
# ---------------------------------------------------------------------------

class TestPIIDetection:
    def test_email_detected(self):
        findings = _scan_value_for_pii("user@example.com", "query:email")
        assert any(f.detector == "email" for f in findings)

    def test_ssn_detected(self):
        findings = _scan_value_for_pii("123-45-6789", "query:ssn")
        assert any(f.detector == "ssn" for f in findings)

    def test_luhn_valid_credit_card(self):
        # Visa test number
        assert _luhn_valid("4111111111111111")

    def test_luhn_invalid_number(self):
        assert not _luhn_valid("1234567890123456")

    def test_credit_card_detected(self):
        findings = _scan_value_for_pii("4111111111111111", "query:cc")
        assert any(f.detector == "credit_card" for f in findings)

    def test_phone_detected(self):
        findings = _scan_value_for_pii("+1-800-555-1234", "query:phone")
        assert any(f.detector == "phone" for f in findings)

    def test_clean_value_no_pii(self):
        findings = _scan_value_for_pii("hello-world", "query:q")
        assert findings == []


# ---------------------------------------------------------------------------
# Secret detection
# ---------------------------------------------------------------------------

class TestSecretDetection:
    def test_aws_key_detected(self):
        findings = _scan_value_for_secrets("AKIAIOSFODNN7EXAMPLE", "query:api_key")
        assert len(findings) > 0
        assert any("AWS" in f.detector or "Key" in f.detector for f in findings)

    def test_github_token_detected(self):
        findings = _scan_value_for_secrets("ghp_" + "a" * 36, "query:token")
        assert len(findings) > 0

    def test_clean_value_no_secrets(self):
        findings = _scan_value_for_secrets("hello", "query:q")
        assert findings == []


# ---------------------------------------------------------------------------
# Policy wiring
# ---------------------------------------------------------------------------

class TestPolicyWiring:
    def test_strict_raises_on_secret(self):
        url = "https://api.example.com/data?api_key=AKIAIOSFODNN7EXAMPLE"
        from unittest.mock import patch
        with patch("safe_fetch._request_guard.check_ssrf"):
            with pytest.raises(SecretLeakError):
                scan_request(url, {}, Policy.STRICT)

    def test_strict_raises_on_pii(self):
        url = "https://example.com/lookup?email=user@example.com"
        from unittest.mock import patch
        with patch("safe_fetch._request_guard.check_ssrf"):
            with pytest.raises(PIILeakError):
                scan_request(url, {}, Policy.STRICT)

    def test_warn_returns_findings_no_raise(self):
        url = "https://example.com/lookup?email=user@example.com"
        from unittest.mock import patch
        with patch("safe_fetch._request_guard.check_ssrf"):
            findings = scan_request(url, {}, Policy.WARN)
        assert len(findings) > 0

    def test_permissive_returns_findings_no_raise(self):
        url = "https://example.com/lookup?email=user@example.com"
        from unittest.mock import patch
        with patch("safe_fetch._request_guard.check_ssrf"):
            findings = scan_request(url, {}, Policy.PERMISSIVE)
        assert len(findings) > 0

    def test_ssrf_always_raises_even_permissive(self):
        with pytest.raises(SSRFBlockedError):
            scan_request("http://192.168.1.1/", {}, Policy.PERMISSIVE)

    def test_clean_url_no_findings(self):
        from unittest.mock import patch
        with patch("safe_fetch._request_guard.check_ssrf"):
            findings = scan_request("https://example.com/page", {}, Policy.STRICT)
        assert findings == []

    def test_header_secret_detected(self):
        from unittest.mock import patch
        with patch("safe_fetch._request_guard.check_ssrf"):
            with pytest.raises(SecretLeakError):
                scan_request(
                    "https://example.com/",
                    {"Authorization": "Bearer ghp_" + "a" * 36},
                    Policy.STRICT,
                )
