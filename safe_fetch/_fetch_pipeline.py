"""Fetch pipeline: content negotiation → .md probe → trafilatura → fallback."""
from __future__ import annotations

import asyncio
import logging
from urllib.parse import urljoin, urlparse, urlunparse

import httpx

from ._exceptions import (
    FetchTimeoutError,
    HTTPStatusError,
    RedirectLimitError,
    ResponseTooLargeError,
    UnsupportedContentTypeError,
)
from ._extractor import extract, record_rendered_text_delta, rendered_visible_text
from ._request_guard import check_ssrf
from ._transport import SafeFetchAsyncHTTPTransport
from ._types import SafeFetchConfig
from ._url import canonicalize_url

log = logging.getLogger(__name__)

_ACCEPT_HEADER = "text/markdown, text/plain;q=0.9, text/html;q=0.8"
_EXTRACTION_SEMAPHORES: dict[int, asyncio.Semaphore] = {}


def _validate_redirect(url: str, config: SafeFetchConfig) -> None:
    """Validate a redirect target URL through scheme and SSRF checks."""
    canonicalize_url(url, config)
    check_ssrf(url, config)


def _build_md_url(url: str) -> str | None:
    """Return url with .md appended to path, or None if already ends in .md."""
    parsed = urlparse(url)
    if parsed.path.endswith(".md"):
        return None
    new_path = parsed.path.rstrip("/") + ".md"
    return urlunparse(parsed._replace(path=new_path))


async def _try_md_probe(md_url: str, client: httpx.AsyncClient, config: SafeFetchConfig) -> str | None:
    """GET md_url; return text if 200 + markdown/plain content-type, else None."""
    try:
        canonicalize_url(md_url, config)
        check_ssrf(md_url, config)
        response = await client.get(md_url)
    except Exception:
        return None
    if response.status_code != 200:
        return None
    ct = response.headers.get("content-type", "")
    if "text/markdown" in ct or "text/plain" in ct:
        return await _read_response_text(response, config)
    return None


def _content_type_allowed(content_type: str, config: SafeFetchConfig) -> bool:
    media_type = content_type.split(";", 1)[0].strip().lower()
    return media_type in {value.lower() for value in config.allowed_content_types}


def _status_allowed(status_code: int, config: SafeFetchConfig) -> bool:
    policy = config.http_status_policy.lower()
    if policy == "all":
        return True
    if policy == "2xx":
        return 200 <= status_code <= 299
    if policy == "2xx,3xx":
        return 200 <= status_code <= 399
    if policy == "2xx,4xx":
        return 200 <= status_code <= 299 or 400 <= status_code <= 499
    return status_code == 200


async def _read_response_text(response: httpx.Response, config: SafeFetchConfig) -> str:
    chunks: list[bytes] = []
    total = 0
    async for chunk in response.aiter_bytes():
        total += len(chunk)
        if total > config.max_response_bytes:
            await response.aclose()
            raise ResponseTooLargeError(
                f"Response exceeded max_response_bytes={config.max_response_bytes}",
                limit=config.max_response_bytes,
            )
        chunks.append(chunk)
    return b"".join(chunks).decode(response.encoding or "utf-8", errors="replace")


def _extraction_semaphore(config: SafeFetchConfig) -> asyncio.Semaphore:
    limit = max(1, config.max_extraction_workers)
    semaphore = _EXTRACTION_SEMAPHORES.get(limit)
    if semaphore is None:
        semaphore = asyncio.Semaphore(limit)
        _EXTRACTION_SEMAPHORES[limit] = semaphore
    return semaphore


async def _extract_with_limit(
    html: str,
    *,
    url: str,
    status_code: int,
    config: SafeFetchConfig,
) -> tuple[str, str]:
    safety_events = getattr(config, "_safety_events", None)
    async with _extraction_semaphore(config):
        rendered_text = await rendered_visible_text(html) if config.rendered_text_mode else None
        content, method = await asyncio.to_thread(
            extract,
            html,
            url=url,
            status_code=status_code,
            safety_events=safety_events,
        )
        if config.rendered_text_mode:
            record_rendered_text_delta(content, rendered_text, safety_events)
        return content, method


def _enforce_response_policy(response: httpx.Response, config: SafeFetchConfig) -> None:
    if not _status_allowed(response.status_code, config):
        raise HTTPStatusError(
            f"HTTP status {response.status_code} rejected by policy {config.http_status_policy!r}",
            status_code=response.status_code,
        )
    content_type = response.headers.get("content-type", "")
    if not _content_type_allowed(content_type, config):
        raise UnsupportedContentTypeError(
            f"Content type {content_type!r} is not allowed",
            content_type=content_type,
        )


async def fetch(url: str, config: SafeFetchConfig) -> tuple[str, str, str, int]:
    """
    Fetch URL and return (content, final_url, extraction_method, status_code).

    Raises FetchTimeoutError, SSRFBlockedError, ExtractionFailedError.
    """
    timeout = httpx.Timeout(connect=config.connect_timeout, read=config.read_timeout, write=10.0, pool=10.0)

    headers = {
        "Accept": _ACCEPT_HEADER,
        "User-Agent": config.user_agent,
        **config.extra_headers,
    }

    async def _fetch() -> tuple[str, str, str, int]:
        async with httpx.AsyncClient(
            timeout=timeout,
            follow_redirects=False,
            headers=headers,
            transport=SafeFetchAsyncHTTPTransport(config),
        ) as client:
            current_url = canonicalize_url(url, config).url
            hop = 0
            redirect_chain: list[dict[str, str]] = []

            while True:
                try:
                    response = await client.get(current_url)
                except httpx.ConnectTimeout as exc:
                    raise FetchTimeoutError(
                        f"Connection timed out after {config.connect_timeout}s for {current_url!r}",
                        phase="connect",
                    ) from exc
                except httpx.ReadTimeout as exc:
                    raise FetchTimeoutError(
                        f"Read timed out after {config.read_timeout}s for {current_url!r}",
                        phase="read",
                    ) from exc
                except httpx.TimeoutException as exc:
                    raise FetchTimeoutError(
                        f"Request timed out for {current_url!r}",
                        phase="unknown",
                    ) from exc

                if response.is_redirect:
                    if hop >= config.max_redirects:
                        raise RedirectLimitError(
                            f"Too many redirects (>{config.max_redirects}) for {url!r}",
                            redirects=hop + 1,
                        )
                    next_url = (
                        str(response.next_request.url)
                        if response.next_request
                        else urljoin(str(response.url), response.headers.get("location", ""))
                    )
                    _validate_redirect(next_url, config)
                    redirect_chain.append({"from": current_url, "to": canonicalize_url(next_url, config).url})
                    current_url = canonicalize_url(next_url, config).url
                    hop += 1
                    continue

                final_url = str(response.url)
                status_code = response.status_code
                content_type = response.headers.get("content-type", "")
                content_length = response.headers.get("content-length")
                setattr(
                    config,
                    "_fetch_metadata",
                    {
                        "content_type": content_type,
                        "content_length": int(content_length) if content_length and content_length.isdigit() else None,
                        "etag": response.headers.get("etag"),
                        "last_modified": response.headers.get("last-modified"),
                        "redirect_chain": redirect_chain,
                    },
                )
                _enforce_response_policy(response, config)

                # Content negotiation: markdown or plain text — return directly
                if "text/markdown" in content_type or "text/plain" in content_type:
                    return await _read_response_text(response, config), final_url, "content-negotiation", status_code

                # HTML path: fire .md probe while extraction runs in a worker thread.
                html = await _read_response_text(response, config)
                md_url = _build_md_url(current_url)
                extraction_task = asyncio.create_task(
                    _extract_with_limit(html, url=final_url, status_code=status_code, config=config)
                )
                probe_task = asyncio.create_task(_try_md_probe(md_url, client, config)) if md_url else None

                if probe_task is None:
                    content, method = await extraction_task
                    return content, final_url, method, status_code

                extraction_result, probe_result = await asyncio.gather(
                    extraction_task,
                    probe_task,
                    return_exceptions=True,
                )

                if probe_result is not None and not isinstance(probe_result, Exception):
                    return probe_result, final_url, "md-probe", status_code

                if isinstance(extraction_result, Exception):
                    raise extraction_result

                content, method = extraction_result
                return content, final_url, method, status_code

    if config.total_timeout is None:
        return await _fetch()
    try:
        return await asyncio.wait_for(_fetch(), timeout=config.total_timeout)
    except asyncio.TimeoutError as exc:
        raise FetchTimeoutError(
            f"Fetch exceeded total_timeout={config.total_timeout}s for {url!r}",
            phase="total",
        ) from exc
