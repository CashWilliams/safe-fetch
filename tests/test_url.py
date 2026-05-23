"""Tests for canonical URL validation."""
from __future__ import annotations

from unittest.mock import patch

import pytest

from safe_fetch._exceptions import HostPolicyError, InvalidSchemeError, InvalidURLError, SSRFBlockedError
from safe_fetch._request_guard import scan_request
from safe_fetch._types import SafeFetchConfig
from safe_fetch._url import canonicalize_url
from safe_fetch import Policy


@pytest.mark.parametrize(
    "url,expected",
    [
        ("ftp://example.com/", InvalidSchemeError),
        ("https://example.com/#token=abc", InvalidURLError),
        ("https://user:pass@example.com/", InvalidURLError),
        ("https://example.com\\@127.0.0.1/", InvalidURLError),
        ("https://example.com/\x00", InvalidURLError),
        ("https://example.com:99999/", InvalidURLError),
        ("https://[::1", InvalidURLError),
        ("http://2130706433/", InvalidURLError),
        ("http://0177.0.0.1/", InvalidURLError),
        ("http://[::ffff:127.0.0.1]/", InvalidURLError),
    ],
)
def test_canonicalize_rejects_unsafe_urls(url, expected):
    with pytest.raises(expected):
        canonicalize_url(url)


@pytest.mark.parametrize(
    "url",
    [
        "http://localhost/",
        "http://service.local/",
        "http://admin.localhost/",
        "http://192.0.2.1/",
    ],
)
def test_canonicalize_blocks_local_and_non_global_targets(url):
    with pytest.raises(SSRFBlockedError):
        canonicalize_url(url)


def test_canonicalize_normalizes_host_and_preserves_path_query():
    canonical = canonicalize_url("HTTPS://Example.COM/docs?q=1")

    assert canonical.url == "https://example.com/docs?q=1"
    assert canonical.host == "example.com"
    assert canonical.path == "/docs"
    assert canonical.query == "q=1"


def test_http_blocked_when_config_disallows_it():
    with pytest.raises(InvalidURLError):
        canonicalize_url("http://example.com/", SafeFetchConfig(allow_http=False))


def test_host_allowlist_and_deny_precedence():
    canonicalize_url(
        "https://docs.example.com/",
        SafeFetchConfig(allowed_hosts={"docs.example.com"}),
    )

    with pytest.raises(HostPolicyError):
        canonicalize_url(
            "https://blog.example.com/",
            SafeFetchConfig(allowed_hosts={"docs.example.com"}),
        )

    with pytest.raises(HostPolicyError):
        canonicalize_url(
            "https://evil.example.com/",
            SafeFetchConfig(
                allowed_host_suffixes={".example.com"},
                blocked_hosts={"evil.example.com"},
            ),
        )


def test_rejected_url_does_not_call_dns_or_http():
    with (
        patch("socket.getaddrinfo") as getaddrinfo,
        patch("httpx.AsyncClient.get") as http_get,
        pytest.raises(InvalidURLError),
    ):
        scan_request("https://user:pass@example.com/", {}, Policy.PERMISSIVE)

    getaddrinfo.assert_not_called()
    http_get.assert_not_called()
