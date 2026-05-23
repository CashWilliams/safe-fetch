"""Tests for content boundary marker generation and wrapping."""
from __future__ import annotations

import re
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest

from safe_fetch._marker import generate_nonce, wrap_content


# ---------------------------------------------------------------------------
# 4.1 generate_nonce()
# ---------------------------------------------------------------------------

def test_generate_nonce_is_32_char_hex():
    nonce = generate_nonce()
    assert re.fullmatch(r"[0-9a-f]{32}", nonce), f"unexpected nonce: {nonce!r}"


def test_generate_nonce_unique():
    assert generate_nonce() != generate_nonce()


# ---------------------------------------------------------------------------
# 4.2 wrap_content() structure
# ---------------------------------------------------------------------------

def test_wrap_content_opening_tag_attributes():
    ts = datetime(2026, 5, 11, 12, 0, 0, tzinfo=timezone.utc)
    wrapped, nonce = wrap_content("hello world", "https://example.com/", ts)

    assert 'untrusted="true"' in wrapped
    assert 'source="https://example.com/"' in wrapped
    assert 'fetched_at="2026-05-11T12:00:00Z"' in wrapped
    assert f'marker="{nonce}"' in wrapped


def test_wrap_content_closing_tag_has_same_marker():
    ts = datetime(2026, 5, 11, 12, 0, 0, tzinfo=timezone.utc)
    wrapped, nonce = wrap_content("hello world", "https://example.com/", ts)

    assert wrapped.endswith(f'</web_content marker="{nonce}">')


def test_wrap_content_body_is_preserved():
    ts = datetime(2026, 5, 11, 12, 0, 0, tzinfo=timezone.utc)
    body = "# Title\n\nSome **markdown** content."
    wrapped, _ = wrap_content(body, "https://example.com/", ts)

    assert body in wrapped


def test_wrap_content_starts_with_web_content_tag():
    ts = datetime(2026, 5, 11, 12, 0, 0, tzinfo=timezone.utc)
    wrapped, _ = wrap_content("body", "https://example.com/", ts)

    assert wrapped.startswith("<web_content ")


# ---------------------------------------------------------------------------
# 4.3 HTML escaping of URL attributes
# ---------------------------------------------------------------------------

def test_wrap_content_escapes_ampersand_in_url():
    ts = datetime(2026, 5, 11, 12, 0, 0, tzinfo=timezone.utc)
    wrapped, _ = wrap_content("body", "https://example.com/?a=1&b=2", ts)

    assert "&amp;" in wrapped
    assert "source=" in wrapped
    # raw & should not appear in attributes
    assert 'source="https://example.com/?a=1&b=2"' not in wrapped


def test_wrap_content_escapes_quotes_in_url():
    ts = datetime(2026, 5, 11, 12, 0, 0, tzinfo=timezone.utc)
    wrapped, _ = wrap_content("body", 'https://example.com/?q="hello"', ts)

    assert "&quot;" in wrapped


# ---------------------------------------------------------------------------
# 4.4 Integration: safe_fetch() produces wrapped result
# ---------------------------------------------------------------------------

async def test_safe_fetch_content_is_wrapped():
    import httpx
    from safe_fetch import safe_fetch

    resp = httpx.Response(
        status_code=200,
        headers={"content-type": "text/markdown"},
        text="# Hello\n\nWorld",
        request=httpx.Request("GET", "https://example.com/"),
    )

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=resp):
        result = await safe_fetch("https://example.com/")

    assert result.content.startswith("<web_content ")
    assert result.content.endswith(f'</web_content marker="{result.content_marker}">')
    assert result.raw_content == "# Hello\n\nWorld"
    assert re.fullmatch(r"[0-9a-f]{32}", result.content_marker)


async def test_safe_fetch_content_marker_in_both_tags():
    import httpx
    from safe_fetch import safe_fetch

    resp = httpx.Response(
        status_code=200,
        headers={"content-type": "text/markdown"},
        text="# Test",
        request=httpx.Request("GET", "https://example.com/"),
    )

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=resp):
        result = await safe_fetch("https://example.com/")

    nonce = result.content_marker
    assert f'marker="{nonce}"' in result.content.split("\n")[0]  # opening tag
    assert result.content.endswith(f'</web_content marker="{nonce}">')


# ---------------------------------------------------------------------------
# 4.5 Nonce uniqueness across two safe_fetch() calls
# ---------------------------------------------------------------------------

async def test_safe_fetch_nonces_are_unique():
    import httpx
    from safe_fetch import safe_fetch

    resp = httpx.Response(
        status_code=200,
        headers={"content-type": "text/markdown"},
        text="# Hello",
        request=httpx.Request("GET", "https://example.com/"),
    )

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=resp):
        result1 = await safe_fetch("https://example.com/")
        result2 = await safe_fetch("https://example.com/")

    assert result1.content_marker != result2.content_marker
