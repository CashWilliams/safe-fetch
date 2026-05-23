"""Tests for connect-time network boundary validation."""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from safe_fetch._exceptions import SSRFBlockedError
from safe_fetch._transport import SafeFetchNetworkBackend
from safe_fetch._types import SafeFetchConfig


def _addrinfo(ip: str):
    return [(0, 0, 0, "", (ip, 443))]


async def test_connect_time_private_ip_is_blocked_before_tcp_connect():
    backend = SafeFetchNetworkBackend(SafeFetchConfig())
    backend._backend.connect_tcp = AsyncMock()

    with (
        patch("socket.getaddrinfo", return_value=_addrinfo("10.0.0.1")),
        pytest.raises(SSRFBlockedError),
    ):
        await backend.connect_tcp("example.com", 443)

    backend._backend.connect_tcp.assert_not_called()


async def test_connect_time_mixed_dns_answers_are_blocked():
    backend = SafeFetchNetworkBackend(SafeFetchConfig())
    backend._backend.connect_tcp = AsyncMock()

    with (
        patch("socket.getaddrinfo", return_value=_addrinfo("8.8.8.8") + _addrinfo("127.0.0.1")),
        pytest.raises(SSRFBlockedError),
    ):
        await backend.connect_tcp("example.com", 443)

    backend._backend.connect_tcp.assert_not_called()


async def test_connect_time_public_ip_is_pinned_for_tcp_connect():
    stream = object()
    backend = SafeFetchNetworkBackend(SafeFetchConfig())
    backend._backend.connect_tcp = AsyncMock(return_value=stream)

    with patch("socket.getaddrinfo", return_value=_addrinfo("8.8.8.8")):
        result = await backend.connect_tcp("example.com", 443)

    assert result is stream
    backend._backend.connect_tcp.assert_awaited_once()
    assert backend._backend.connect_tcp.await_args.args[:2] == ("8.8.8.8", 443)
