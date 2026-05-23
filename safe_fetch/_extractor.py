"""HTML content extraction: trafilatura primary, readability+markdownify fallback."""
from __future__ import annotations

import re
from contextlib import suppress

from ._exceptions import ExtractionFailedError
from ._types import SafetyEvent

# Matches a negative coordinate value used for off-screen positioning tricks
_NEGATIVE_COORD_RE = re.compile(r"(?:left|top):-\d")
_OFFSCREEN_COORD_RE = re.compile(r"(?:left|top|right|bottom):-\d")
_ZERO_DIMENSION_RE = re.compile(r"(?:width|height):(0|0px|0em|0rem|0%)")
_HIDDEN_SELECTOR_RE = re.compile(r"([.#])([A-Za-z0-9_-]+)\s*\{([^{}]+)\}", re.DOTALL)


def _style_is_hidden(style: str) -> bool:
    style = re.sub(r"\s*:\s*", ":", style)
    style = re.sub(r"\s*;\s*", ";", style).lower()
    return (
        "display:none" in style
        or "visibility:hidden" in style
        or "opacity:0" in style
        or "font-size:0" in style
        or "font-size:0px" in style
        or "clip:" in style
        or "clip-path:" in style
        or "color:transparent" in style
        or "rgba(0,0,0,0)" in style
        or "transform:scale(0" in style
        or "transform:translate" in style
        or bool(_ZERO_DIMENSION_RE.search(style))
        or (
            ("position:absolute" in style or "position:fixed" in style)
            and bool(_OFFSCREEN_COORD_RE.search(style))
        )
    )


def _record_event(events: list[SafetyEvent] | None, category: str, count: int) -> None:
    if events is not None and count:
        events.append(
            SafetyEvent(
                category="html_sanitizer",
                action=category,
                count=count,
                message=f"Removed {count} hidden/non-rendered HTML element(s)",
            )
        )


def sanitize_html(html: str, safety_events: list[SafetyEvent] | None = None) -> str:
    """Strip invisible and non-rendered content from HTML before extraction.

    Removes:
    - Elements hidden via inline CSS (display:none, visibility:hidden, opacity:0,
      font-size:0, off-screen absolute/fixed positioning)
    - Elements with the HTML5 `hidden` attribute
    - HTML comments
    - <script>, <template>, <noscript> elements
    """
    from bs4 import BeautifulSoup, Comment

    soup = BeautifulSoup(html, "lxml")

    removal_counts: dict[str, int] = {}

    # --- Page-local hidden class/id selectors ---
    hidden_classes: set[str] = set()
    hidden_ids: set[str] = set()
    for style_tag in soup.find_all("style"):
        css = style_tag.get_text(" ")
        for selector_type, name, body in _HIDDEN_SELECTOR_RE.findall(css):
            if _style_is_hidden(body):
                if selector_type == ".":
                    hidden_classes.add(name)
                else:
                    hidden_ids.add(name)
        style_tag.decompose()

    for class_name in hidden_classes:
        for tag in soup.find_all(class_=lambda value: value and class_name in (value if isinstance(value, list) else str(value).split())):
            tag.decompose()
            removal_counts["stylesheet_hidden"] = removal_counts.get("stylesheet_hidden", 0) + 1

    for element_id in hidden_ids:
        for tag in soup.find_all(id=element_id):
            tag.decompose()
            removal_counts["stylesheet_hidden"] = removal_counts.get("stylesheet_hidden", 0) + 1

    # --- CSS inline style vectors ---
    for tag in soup.find_all(style=True):
        # Normalize: remove spaces around : and ;, lowercase
        if not getattr(tag, "attrs", None):
            continue
        raw_style = tag.get("style") or ""
        if _style_is_hidden(raw_style):
            tag.decompose()
            removal_counts["inline_hidden"] = removal_counts.get("inline_hidden", 0) + 1

    # --- HTML5 hidden attribute ---
    for tag in soup.find_all(hidden=True):
        tag.decompose()
        removal_counts["hidden_attribute"] = removal_counts.get("hidden_attribute", 0) + 1

    for tag in soup.find_all(attrs={"aria-hidden": True}):
        tag.decompose()
        removal_counts["hidden_attribute"] = removal_counts.get("hidden_attribute", 0) + 1

    for tag in soup.find_all(attrs={"inert": True}):
        tag.decompose()
        removal_counts["hidden_attribute"] = removal_counts.get("hidden_attribute", 0) + 1

    for tag in soup.find_all("input", attrs={"type": lambda value: value and str(value).lower() == "hidden"}):
        tag.decompose()
        removal_counts["hidden_input"] = removal_counts.get("hidden_input", 0) + 1

    # --- Non-rendered structural elements ---
    for tag in soup.find_all(["script", "template", "noscript", "desc", "title", "foreignObject", "foreignobject"]):
        tag.decompose()
        removal_counts["structural_hidden"] = removal_counts.get("structural_hidden", 0) + 1

    # --- HTML comments ---
    for comment in soup.find_all(string=lambda text: isinstance(text, Comment)):
        comment.extract()
        removal_counts["comment"] = removal_counts.get("comment", 0) + 1

    for category, count in removal_counts.items():
        _record_event(safety_events, category, count)

    return str(soup)


def extract(
    html: str,
    url: str = "",
    status_code: int = 200,
    safety_events: list[SafetyEvent] | None = None,
) -> tuple[str, str]:
    """
    Extract main content from HTML as markdown.

    Returns (content, extraction_method).
    Raises ExtractionFailedError if all extractors fail.
    """
    html = sanitize_html(html, safety_events=safety_events)

    # Primary: trafilatura
    result = _try_trafilatura(html)
    if result is not None:
        return result, "trafilatura"

    # Fallback: readability-lxml + markdownify
    result = _try_readability_markdownify(html)
    if result is not None:
        return result, "readability+markdownify"

    raise ExtractionFailedError(
        f"All extraction methods failed for {url!r}",
        url=url,
        status_code=status_code,
    )


async def rendered_visible_text(html: str) -> str | None:
    """Return browser-rendered visible text when Playwright is installed."""
    try:
        from playwright.async_api import async_playwright
    except Exception:
        return None

    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch()
        try:
            page = await browser.new_page()
            await page.set_content(html)
            return await page.locator("body").inner_text()
        finally:
            with suppress(Exception):
                await browser.close()


def record_rendered_text_delta(
    parser_text: str,
    rendered_text: str | None,
    safety_events: list[SafetyEvent] | None,
) -> None:
    """Record an event when parser output contains text absent from rendered output."""
    if safety_events is None:
        return
    if rendered_text is None:
        safety_events.append(
            SafetyEvent(
                category="html_sanitizer",
                action="rendered_text_unavailable",
                severity="warning",
                message="Playwright rendered text extraction is unavailable",
            )
        )
        return

    parser_words = {word.lower() for word in re.findall(r"\w{4,}", parser_text)}
    rendered_words = {word.lower() for word in re.findall(r"\w{4,}", rendered_text)}
    hidden_delta = parser_words - rendered_words
    if hidden_delta:
        safety_events.append(
            SafetyEvent(
                category="html_sanitizer",
                action="rendered_text_delta",
                severity="warning",
                count=len(hidden_delta),
                message="Parser-extracted text contains terms absent from rendered visible text",
            )
        )


def _try_trafilatura(html: str) -> str | None:
    try:
        import trafilatura

        return trafilatura.extract(html, output_format="markdown")
    except Exception:
        return None


def _try_readability_markdownify(html: str) -> str | None:
    try:
        from markdownify import markdownify
        from readability import Document

        doc = Document(html)
        article_html = doc.summary()
        if not article_html:
            return None
        md = markdownify(article_html, heading_style="ATX")
        return md.strip() or None
    except Exception:
        return None
