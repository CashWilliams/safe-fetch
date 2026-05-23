"""Network-boundary enforcing httpx transport."""
from __future__ import annotations

import socket
import typing
import ipaddress

import httpcore
import httpx
from httpcore._backends.auto import AutoBackend
from httpcore._backends.base import SOCKET_OPTION, AsyncNetworkBackend, AsyncNetworkStream
from httpx._config import DEFAULT_LIMITS, Limits, create_ssl_context
from httpx._transports.default import AsyncResponseStream, map_httpcore_exceptions

from ._types import SafeFetchConfig
from ._url import canonicalize_url, enforce_ip_policy


class SafeFetchNetworkBackend(AsyncNetworkBackend):
    """Resolve, validate, and pin TCP connections to validated addresses."""

    def __init__(self, config: SafeFetchConfig) -> None:
        self._config = config
        self._backend = AutoBackend()

    async def connect_tcp(
        self,
        host: str,
        port: int,
        timeout: float | None = None,
        local_address: str | None = None,
        socket_options: typing.Iterable[SOCKET_OPTION] | None = None,
    ) -> AsyncNetworkStream:
        hostname = host.decode("ascii") if isinstance(host, bytes) else host
        canonical = canonicalize_url(f"https://{hostname}:{port}/", self._config)

        results = socket.getaddrinfo(
            canonical.host,
            port,
            type=socket.SOCK_STREAM,
        )
        if not results:
            raise httpcore.ConnectError(f"DNS resolution returned no addresses for {canonical.host!r}")

        resolved_ips: list[str] = []
        for result in results:
            ip = result[4][0]
            resolved_ips.append(ip)
            enforce_ip_policy(ipaddress.ip_address(ip), canonical.host, self._config)

        return await self._backend.connect_tcp(
            resolved_ips[0],
            port,
            timeout=timeout,
            local_address=local_address,
            socket_options=socket_options,
        )

    async def connect_unix_socket(
        self,
        path: str,
        timeout: float | None = None,
        socket_options: typing.Iterable[SOCKET_OPTION] | None = None,
    ) -> AsyncNetworkStream:
        return await self._backend.connect_unix_socket(
            path,
            timeout=timeout,
            socket_options=socket_options,
        )

    async def sleep(self, seconds: float) -> None:
        await self._backend.sleep(seconds)


class SafeFetchAsyncHTTPTransport(httpx.AsyncBaseTransport):
    """Minimal async HTTP transport with a SafeFetch network backend."""

    def __init__(
        self,
        config: SafeFetchConfig,
        *,
        verify: typing.Any = True,
        cert: typing.Any = None,
        trust_env: bool = True,
        http1: bool = True,
        http2: bool = False,
        limits: Limits = DEFAULT_LIMITS,
    ) -> None:
        ssl_context = create_ssl_context(verify=verify, cert=cert, trust_env=trust_env)
        self._pool = httpcore.AsyncConnectionPool(
            ssl_context=ssl_context,
            max_connections=limits.max_connections,
            max_keepalive_connections=limits.max_keepalive_connections,
            keepalive_expiry=limits.keepalive_expiry,
            http1=http1,
            http2=http2,
            network_backend=SafeFetchNetworkBackend(config),
        )

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        req = httpcore.Request(
            method=request.method,
            url=httpcore.URL(
                scheme=request.url.raw_scheme,
                host=request.url.raw_host,
                port=request.url.port,
                target=request.url.raw_path,
            ),
            headers=request.headers.raw,
            content=request.stream,
            extensions=request.extensions,
        )
        with map_httpcore_exceptions():
            resp = await self._pool.handle_async_request(req)

        return httpx.Response(
            status_code=resp.status,
            headers=resp.headers,
            stream=AsyncResponseStream(resp.stream),
            extensions=resp.extensions,
        )

    async def aclose(self) -> None:
        await self._pool.aclose()
