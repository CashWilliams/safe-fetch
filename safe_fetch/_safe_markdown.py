"""Safe Markdown transformation for LLM-ready output."""
from __future__ import annotations

import re

from ._types import SafeFetchConfig, SafetyEvent
from ._url import canonicalize_url

_HTML_COMMENT_RE = re.compile(r"<!--.*?-->", re.DOTALL)
_RAW_BLOCK_RE = re.compile(
    r"<\s*(script|style|svg|template|noscript)\b.*?>.*?<\s*/\s*\1\s*>",
    re.IGNORECASE | re.DOTALL,
)
_HTML_TAG_RE = re.compile(r"<[^>\n]+>")
_IMAGE_RE = re.compile(r"!\[([^\]]*)\]\(([^)]*)\)")
_REFERENCE_IMAGE_RE = re.compile(r"!\[([^\]]*)\]\[([^\]]*)\]")
_REFERENCE_DEF_RE = re.compile(r"^\s*\[([^\]]+)\]:\s*(\S+).*$", re.MULTILINE)
_LINK_RE = re.compile(r"(?<!!)\[([^\]]+)\]\(([^)]*)\)")
_AUTOLINK_RE = re.compile(r"<(https?://[^>\s]+)>", re.IGNORECASE)


def _event(action: str, count: int) -> SafetyEvent:
    return SafetyEvent(
        category="safe_markdown",
        action=action,
        count=count,
        message=f"Neutralized {count} Markdown construct(s)",
    )


def _sub_count(pattern: re.Pattern[str], repl: str | re.Match[str], text: str) -> tuple[str, int]:
    return pattern.subn(repl, text)


def _link_allowed(href: str, config: SafeFetchConfig) -> bool:
    try:
        canonicalize_url(href, config)
    except Exception:
        return False
    return True


def transform_safe_markdown(
    markdown: str,
    config: SafeFetchConfig,
) -> tuple[str, list[SafetyEvent]]:
    """Return neutralized Markdown and safety events."""
    events: list[SafetyEvent] = []
    output = markdown

    output, count = _sub_count(_HTML_COMMENT_RE, "", output)
    if count:
        events.append(_event("remove_html_comments", count))

    output, count = _sub_count(_RAW_BLOCK_RE, "", output)
    if count:
        events.append(_event("remove_raw_blocks", count))

    output, count = _sub_count(_IMAGE_RE, lambda match: match.group(1) or "[image removed]", output)
    if count:
        events.append(_event("neutralize_images", count))

    output, count = _sub_count(
        _REFERENCE_IMAGE_RE,
        lambda match: match.group(1) or "[image removed]",
        output,
    )
    if count:
        events.append(_event("neutralize_reference_images", count))

    output, count = _sub_count(_REFERENCE_DEF_RE, "", output)
    if count:
        events.append(_event("remove_reference_definitions", count))

    def replace_link(match: re.Match[str]) -> str:
        text = match.group(1)
        href = match.group(2)
        if _link_allowed(href, config):
            return text
        return text

    output, count = _sub_count(_LINK_RE, replace_link, output)
    if count:
        events.append(_event("neutralize_links", count))

    output, count = _sub_count(_AUTOLINK_RE, lambda match: match.group(1), output)
    if count:
        events.append(_event("neutralize_autolinks", count))

    output, count = _sub_count(_HTML_TAG_RE, "", output)
    if count:
        events.append(_event("remove_raw_html", count))

    return output, events
