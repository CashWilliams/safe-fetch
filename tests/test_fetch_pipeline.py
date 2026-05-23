"""Unit tests for fetch pipeline (mocked httpx responses)."""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

import httpx
import pytest

from safe_fetch._exceptions import (
    FetchTimeoutError,
    HTTPStatusError,
    RedirectLimitError,
    ResponseTooLargeError,
    SSRFBlockedError,
    UnsupportedContentTypeError,
)
from safe_fetch._fetch_pipeline import _build_md_url, _extract_with_limit, fetch
from safe_fetch._types import SafeFetchConfig


def _make_response(content_type: str, body: str, status: int = 200, url: str = "https://example.com/") -> httpx.Response:
    return httpx.Response(
        status_code=status,
        headers={"content-type": content_type},
        text=body,
        request=httpx.Request("GET", url),
    )


@pytest.fixture
def config():
    return SafeFetchConfig()


# ---------------------------------------------------------------------------
# Content negotiation
# ---------------------------------------------------------------------------

class TestContentNegotiation:
    async def test_markdown_response_returned_directly(self, config):
        md_body = "# Hello\n\nThis is markdown."
        response = _make_response("text/markdown; charset=utf-8", md_body)

        with patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=response):
            content, final_url, method, status = await fetch("https://example.com/", config)

        assert method == "content-negotiation"
        assert content == md_body

    async def test_plain_text_response_returned_directly(self, config):
        plain_body = "Just some plain text."
        response = _make_response("text/plain", plain_body)

        with patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=response):
            content, final_url, method, status = await fetch("https://example.com/", config)

        assert method == "content-negotiation"
        assert content == plain_body


# ---------------------------------------------------------------------------
# Timeout handling
# ---------------------------------------------------------------------------

class TestTimeouts:
    async def test_connect_timeout_raises_fetch_timeout_error(self, config):
        with patch(
            "httpx.AsyncClient.get",
            new_callable=AsyncMock,
            side_effect=httpx.ConnectTimeout("timed out"),
        ):
            with pytest.raises(FetchTimeoutError) as exc_info:
                await fetch("https://example.com/", config)
            assert exc_info.value.phase == "connect"

    async def test_read_timeout_raises_fetch_timeout_error(self, config):
        with patch(
            "httpx.AsyncClient.get",
            new_callable=AsyncMock,
            side_effect=httpx.ReadTimeout("timed out"),
        ):
            with pytest.raises(FetchTimeoutError) as exc_info:
                await fetch("https://example.com/", config)
            assert exc_info.value.phase == "read"

    async def test_total_timeout_raises_fetch_timeout_error(self, config):
        config.total_timeout = 0.01

        async def slow_get(url, **kwargs):
            await __import__("asyncio").sleep(1)
            return _make_response("text/plain", "late")

        with patch("httpx.AsyncClient.get", new_callable=AsyncMock, side_effect=slow_get):
            with pytest.raises(FetchTimeoutError) as exc_info:
                await fetch("https://example.com/", config)
            assert exc_info.value.phase == "total"


# ---------------------------------------------------------------------------
# Resource and response policy controls
# ---------------------------------------------------------------------------

class TestResourceControls:
    async def test_response_too_large_raises(self, config):
        config.max_response_bytes = 5
        response = _make_response("text/plain", "0123456789")

        with patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=response):
            with pytest.raises(ResponseTooLargeError):
                await fetch("https://example.com/", config)

    async def test_404_rejected_by_default(self, config):
        response = _make_response("text/plain", "not found", status=404)

        with patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=response):
            with pytest.raises(HTTPStatusError) as exc_info:
                await fetch("https://example.com/missing", config)

        assert exc_info.value.status_code == 404

    async def test_404_allowed_by_policy(self, config):
        config.http_status_policy = "2xx,4xx"
        response = _make_response("text/plain", "not found", status=404)

        with patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=response):
            content, final_url, method, status = await fetch("https://example.com/missing", config)

        assert content == "not found"
        assert status == 404

    async def test_unsupported_content_type_raises(self, config):
        response = _make_response("image/png", "png bytes")

        with patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=response):
            with pytest.raises(UnsupportedContentTypeError):
                await fetch("https://example.com/image.png", config)

    async def test_extraction_worker_limit(self, config):
        import asyncio

        config.max_extraction_workers = 1
        running = 0
        max_running = 0

        def slow_extract(html, *, url, status_code, safety_events=None):
            nonlocal running, max_running
            running += 1
            max_running = max(max_running, running)
            __import__("time").sleep(0.02)
            running -= 1
            return html, "mock"

        with patch("safe_fetch._fetch_pipeline.extract", side_effect=slow_extract):
            await asyncio.gather(
                _extract_with_limit("a", url="https://example.com/a", status_code=200, config=config),
                _extract_with_limit("b", url="https://example.com/b", status_code=200, config=config),
            )

        assert max_running == 1


# ---------------------------------------------------------------------------
# Redirect handling
# ---------------------------------------------------------------------------

class TestRedirects:
    async def test_normal_redirect_chain_followed(self, config):
        first = httpx.Response(
            302,
            headers={"location": "/step-1"},
            request=httpx.Request("GET", "https://example.com/start"),
        )
        second = httpx.Response(
            302,
            headers={"location": "https://example.com/final"},
            request=httpx.Request("GET", "https://example.com/step-1"),
        )
        final = _make_response(
            "text/markdown",
            "# Final",
            url="https://example.com/final",
        )
        responses = [first, second, final]

        async def mock_get(url, **kwargs):
            return responses.pop(0)

        with (
            patch("httpx.AsyncClient.get", new_callable=AsyncMock, side_effect=mock_get),
            patch("safe_fetch._fetch_pipeline.check_ssrf"),
        ):
            content, final_url, method, status = await fetch("https://example.com/start", config)

        assert content == "# Final"
        assert final_url == "https://example.com/final"
        assert method == "content-negotiation"

    async def test_redirect_to_private_ip_blocked(self, config):
        redirect = httpx.Response(
            302,
            headers={"location": "http://192.168.1.1/admin"},
            request=httpx.Request("GET", "https://example.com/start"),
        )

        with patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=redirect):
            with pytest.raises(SSRFBlockedError):
                await fetch("https://example.com/start", config)

    async def test_redirect_limit_raises_redirect_limit_error(self, config):
        async def mock_get(url, **kwargs):
            return httpx.Response(
                302,
                headers={"location": f"{url}/next"},
                request=httpx.Request("GET", url),
            )

        with (
            patch("httpx.AsyncClient.get", new_callable=AsyncMock, side_effect=mock_get),
            patch("safe_fetch._fetch_pipeline.check_ssrf"),
        ):
            with pytest.raises(RedirectLimitError) as exc_info:
                await fetch("https://example.com/start", config)

        assert exc_info.value.redirects == 6


# ---------------------------------------------------------------------------
# HTML extraction fallthrough
# ---------------------------------------------------------------------------

class TestHTMLExtraction:
    async def test_html_falls_through_to_trafilatura(self, config):
        html = """
        <html><body>
        <article><h1>Title</h1><p>Some article content here for extraction.</p></article>
        </body></html>
        """
        html_response = _make_response("text/html; charset=utf-8", html)
        md_404 = _make_response("text/plain", "", status=404, url="https://example.com/.md")

        async def mock_get(url, **kwargs):
            if str(url).endswith(".md"):
                return md_404
            return html_response

        with patch("httpx.AsyncClient.get", new_callable=AsyncMock, side_effect=mock_get):
            content, final_url, method, status = await fetch("https://example.com/", config)

        assert method in ("trafilatura", "readability+markdownify")
        assert len(content) > 0


# ---------------------------------------------------------------------------
# _build_md_url
# ---------------------------------------------------------------------------

class TestBuildMdUrl:
    def test_appends_md_to_path(self):
        assert _build_md_url("https://example.com/docs/page") == "https://example.com/docs/page.md"

    def test_preserves_query_string(self):
        result = _build_md_url("https://example.com/docs/page?foo=bar")
        assert result == "https://example.com/docs/page.md?foo=bar"

    def test_returns_none_if_already_md(self):
        assert _build_md_url("https://example.com/README.md") is None

    def test_strips_trailing_slash_before_appending(self):
        result = _build_md_url("https://example.com/docs/page/")
        assert result == "https://example.com/docs/page.md"


# ---------------------------------------------------------------------------
# .md probe
# ---------------------------------------------------------------------------

class TestMdProbe:
    async def test_probe_success_used_over_html_extraction(self, config):
        html = "<html><body><article><p>Original content</p></article></body></html>"
        md_content = "# Markdown version\n\nClean content."
        html_response = _make_response("text/html", html)
        md_response = _make_response("text/markdown", md_content, url="https://example.com/page.md")

        async def mock_get(url, **kwargs):
            if str(url).endswith(".md"):
                return md_response
            return html_response

        with patch("httpx.AsyncClient.get", new_callable=AsyncMock, side_effect=mock_get):
            content, final_url, method, status = await fetch("https://example.com/page", config)

        assert method == "md-probe"
        assert content == md_content

    async def test_probe_404_falls_through(self, config):
        html = "<html><body><article><h1>Title</h1><p>Some content here.</p></article></body></html>"
        html_response = _make_response("text/html", html)
        md_404 = _make_response("text/plain", "", status=404)

        async def mock_get(url, **kwargs):
            if str(url).endswith(".md"):
                return md_404
            return html_response

        with patch("httpx.AsyncClient.get", new_callable=AsyncMock, side_effect=mock_get):
            content, final_url, method, status = await fetch("https://example.com/page", config)

        assert method in ("trafilatura", "readability+markdownify")

    async def test_probe_html_content_type_rejected(self, config):
        html = "<html><body><article><h1>Title</h1><p>Content here.</p></article></body></html>"
        html_response = _make_response("text/html", html)
        md_html = _make_response("text/html", "<html>some page</html>", url="https://example.com/page.md")

        async def mock_get(url, **kwargs):
            if str(url).endswith(".md"):
                return md_html
            return html_response

        with patch("httpx.AsyncClient.get", new_callable=AsyncMock, side_effect=mock_get):
            content, final_url, method, status = await fetch("https://example.com/page", config)

        assert method in ("trafilatura", "readability+markdownify")

    async def test_probe_exception_swallowed(self, config):
        html = "<html><body><article><h1>Title</h1><p>Content here.</p></article></body></html>"
        html_response = _make_response("text/html", html)

        async def mock_get(url, **kwargs):
            if str(url).endswith(".md"):
                raise httpx.ConnectError("refused")
            return html_response

        with patch("httpx.AsyncClient.get", new_callable=AsyncMock, side_effect=mock_get):
            content, final_url, method, status = await fetch("https://example.com/page", config)

        assert method in ("trafilatura", "readability+markdownify")

    async def test_probe_skipped_for_url_already_ending_in_md(self, config):
        md_content = "# Already markdown"
        md_response = _make_response("text/markdown", md_content)
        call_urls = []

        async def mock_get(url, **kwargs):
            call_urls.append(str(url))
            return md_response

        with patch("httpx.AsyncClient.get", new_callable=AsyncMock, side_effect=mock_get):
            content, final_url, method, status = await fetch("https://example.com/README.md", config)

        # Only one request — the primary; no .md.md probe
        assert not any(u.endswith(".md.md") for u in call_urls)
        assert method == "content-negotiation"

    async def test_probe_not_fired_for_content_negotiated_response(self, config):
        md_response = _make_response("text/markdown", "# Direct markdown")
        call_urls = []

        async def mock_get(url, **kwargs):
            call_urls.append(str(url))
            return md_response

        with patch("httpx.AsyncClient.get", new_callable=AsyncMock, side_effect=mock_get):
            content, final_url, method, status = await fetch("https://example.com/page", config)

        assert method == "content-negotiation"
        assert len(call_urls) == 1  # no probe request
