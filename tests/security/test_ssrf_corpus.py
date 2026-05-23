"""Adversarial SSRF and URL parsing corpus."""
from __future__ import annotations

from unittest.mock import patch

import pytest

from safe_fetch import Policy, SafeFetchConfig
from safe_fetch._exceptions import HostPolicyError, InvalidSchemeError, InvalidURLError, SSRFBlockedError
from safe_fetch._request_guard import scan_request
from safe_fetch._transport import SafeFetchNetworkBackend
from safe_fetch._url import canonicalize_url


@pytest.mark.parametrize(
    "url,expected",
    [
        ("https://user:pass@example.com/", InvalidURLError),
        ("https://example.com/#secret", InvalidURLError),
        ("https://example.com\\@169.254.169.254/", InvalidURLError),
        ("http://2130706433/", InvalidURLError),
        ("http://0177.0.0.1/", InvalidURLError),
        ("http://[::ffff:127.0.0.1]/", InvalidURLError),
        ("http://localhost/", SSRFBlockedError),
        ("http://metadata.google.internal.local/", SSRFBlockedError),
        ("http://192.0.2.1/", SSRFBlockedError),
        ("file:///etc/passwd", InvalidSchemeError),
    ],
)
def test_ssrf_bypass_corpus_rejected(url, expected):
    with pytest.raises(expected):
        canonicalize_url(url)


def test_host_allowlist_blocks_unknown_host():
    with pytest.raises(HostPolicyError):
        canonicalize_url(
            "https://blog.example.com/",
            SafeFetchConfig(allowed_hosts={"docs.example.com"}),
        )


def test_generated_invalid_urls_do_not_reach_network_layer():
    invalid_urls = [
        "https://user:pass@example.com/",
        "https://example.com/#token",
        "https://example.com\\@127.0.0.1/",
        "http://2130706433/",
    ]
    for url in invalid_urls:
        with (
            patch("socket.getaddrinfo") as getaddrinfo,
            patch("httpx.AsyncClient.get") as http_get,
            pytest.raises((InvalidURLError, SSRFBlockedError)),
        ):
            scan_request(url, {}, Policy.PERMISSIVE)
        getaddrinfo.assert_not_called()
        http_get.assert_not_called()


async def test_dns_rebinding_connect_time_private_answer_blocks():
    backend = SafeFetchNetworkBackend(SafeFetchConfig())
    backend._backend.connect_tcp = __import__("unittest.mock").mock.AsyncMock()

    with (
        patch("socket.getaddrinfo", return_value=[(0, 0, 0, "", ("10.0.0.5", 443))]),
        pytest.raises(SSRFBlockedError),
    ):
        await backend.connect_tcp("example.com", 443)


async def test_mixed_public_private_dns_answers_block():
    backend = SafeFetchNetworkBackend(SafeFetchConfig())
    backend._backend.connect_tcp = __import__("unittest.mock").mock.AsyncMock()

    with (
        patch(
            "socket.getaddrinfo",
            return_value=[
                (0, 0, 0, "", ("8.8.8.8", 443)),
                (0, 0, 0, "", ("127.0.0.1", 443)),
            ],
        ),
        pytest.raises(SSRFBlockedError),
    ):
        await backend.connect_tcp("example.com", 443)
