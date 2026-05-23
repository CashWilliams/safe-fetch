"""Fetch pipeline: content negotiation → .md probe → trafilatura → fallback."""
from __future__ import annotations

import asyncio
import logging
from urllib.parse import urlparse, urlunparse

import httpx

from ._exceptions import FetchTimeoutError, SSRFBlockedError
from ._extractor import extract
from ._request_guard import check_ssrf, validate_url_scheme
from ._types import SafeFetchConfig

log = logging.getLogger(__name__)

_MAX_REDIRECTS = 5
_ACCEPT_HEADER = "text/markdown, text/plain;q=0.9, text/html;q=0.8"


async def _validate_redirect(url: str) -> None:
    """Validate a redirect target URL through scheme and SSRF checks."""
    validate_url_scheme(url)
    check_ssrf(url)


def _build_md_url(url: str) -> str | None:
    """Return url with .md appended to path, or None if already ends in .md."""
    parsed = urlparse(url)
    if parsed.path.endswith(".md"):
        return None
    new_path = parsed.path.rstrip("/") + ".md"
    return urlunparse(parsed._replace(path=new_path))


async def _try_md_probe(md_url: str, client: httpx.AsyncClient) -> str | None:
    """GET md_url; return text if 200 + markdown/plain content-type, else None."""
    try:
        response = await client.get(md_url)
    except Exception:
        return None
    if response.status_code != 200:
        return None
    ct = response.headers.get("content-type", "")
    if "text/markdown" in ct or "text/plain" in ct:
        return response.text
    return None


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

    async with httpx.AsyncClient(
        timeout=timeout,
        follow_redirects=False,
        headers=headers,
    ) as client:
        current_url = url
        hop = 0

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
                if hop >= _MAX_REDIRECTS:
                    raise FetchTimeoutError(
                        f"Too many redirects (>{_MAX_REDIRECTS}) for {url!r}",
                        phase="redirect",
                    )
                next_url = str(response.next_request.url) if response.next_request else response.headers.get("location", "")
                await _validate_redirect(next_url)
                current_url = next_url
                hop += 1
                continue

            final_url = str(response.url)
            status_code = response.status_code
            content_type = response.headers.get("content-type", "")

            # Content negotiation: markdown or plain text — return directly
            if "text/markdown" in content_type or "text/plain" in content_type:
                return response.text, final_url, "content-negotiation", status_code

            # HTML path: fire .md probe in background while running extraction
            html = response.text
            md_url = _build_md_url(current_url)
            probe_task = asyncio.create_task(_try_md_probe(md_url, client)) if md_url else None

            # Run sync extraction while probe I/O is in flight
            try:
                content, method = extract(html, url=final_url, status_code=status_code)
            except Exception as extraction_exc:
                # Probe may save us — await it before re-raising
                if probe_task is not None:
                    probe_result = await probe_task
                    if probe_result is not None:
                        return probe_result, final_url, "md-probe", status_code
                raise extraction_exc

            # Check probe result (may already be done)
            if probe_task is not None:
                probe_result = await probe_task
                if probe_result is not None:
                    return probe_result, final_url, "md-probe", status_code

            return content, final_url, method, status_code
