"""HTML content extraction: trafilatura primary, readability+markdownify fallback."""
from __future__ import annotations

import re

from ._exceptions import ExtractionFailedError

# Matches a negative coordinate value used for off-screen positioning tricks
_NEGATIVE_COORD_RE = re.compile(r"(?:left|top):-\d")


def sanitize_html(html: str) -> str:
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

    # --- CSS inline style vectors ---
    for tag in soup.find_all(style=True):
        # Normalize: remove spaces around : and ;, lowercase
        if not getattr(tag, "attrs", None):
            continue
        raw_style = tag.get("style") or ""
        style = re.sub(r"\s*:\s*", ":", raw_style)
        style = re.sub(r"\s*;\s*", ";", style).lower()

        hidden = (
            "display:none" in style
            or "visibility:hidden" in style
            or "opacity:0" in style
            or "font-size:0" in style
            or "font-size:0px" in style
            or (
                ("position:absolute" in style or "position:fixed" in style)
                and bool(_NEGATIVE_COORD_RE.search(style))
            )
        )
        if hidden:
            tag.decompose()

    # --- HTML5 hidden attribute ---
    for tag in soup.find_all(hidden=True):
        tag.decompose()

    # --- Non-rendered structural elements ---
    for tag in soup.find_all(["script", "template", "noscript"]):
        tag.decompose()

    # --- HTML comments ---
    for comment in soup.find_all(string=lambda text: isinstance(text, Comment)):
        comment.extract()

    return str(soup)


def extract(html: str, url: str = "", status_code: int = 200) -> tuple[str, str]:
    """
    Extract main content from HTML as markdown.

    Returns (content, extraction_method).
    Raises ExtractionFailedError if all extractors fail.
    """
    html = sanitize_html(html)

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
