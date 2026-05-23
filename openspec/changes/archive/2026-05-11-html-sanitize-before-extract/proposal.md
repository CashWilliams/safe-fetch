## Why

Prompt injection payloads are routinely hidden in web pages using CSS and HTML techniques that are invisible to human visitors but fully extracted by trafilatura and readability, passing injection directly into LLM context. Empirical research (Palo Alto Unit 42, 2025) finds ~70% of in-the-wild injections are embedded in non-rendered HTML. The URL `https://cashwilliams.com/trixie/` demonstrates this: a `<div style="display:none">` containing a multi-paragraph injection payload currently passes through safe-fetch undetected.

## What Changes

- New `sanitize_html()` function in `safe_fetch/_extractor.py` strips invisible/non-rendered content from raw HTML before any extractor sees it
- `extract()` calls `sanitize_html()` as its first step; trafilatura and readability receive sanitized HTML
- **CSS inline style vectors removed** (elements matching any of):
  - `display:none` / `display: none`
  - `visibility:hidden`
  - `opacity:0`
  - `font-size:0` / `font-size:0px`
  - Off-screen positioning: `left:-\d+px` or `top:-\d+px` (regex) combined with `position:absolute` or `position:fixed`
- **HTML structural vectors removed**:
  - HTML comments (`<!-- ... -->`)
  - `hidden` attribute on any element
  - `<script>` tags of any type (including `type="text/plain"`)
  - `<template>` elements
  - `<noscript>` elements
- Uses `BeautifulSoup` with `lxml` parser (already a transitive dependency via `readability-lxml`)
- No new runtime dependencies

## Capabilities

### New Capabilities
- `html-sanitize`: Pre-extraction HTML sanitization — strips CSS-hidden elements, HTML comments, and non-rendered structural elements before content extraction

### Modified Capabilities

## Impact

- `safe_fetch/_extractor.py`: adds `sanitize_html()`, called at the top of `extract()`
- No changes to `_fetch_pipeline.py`, `__init__.py`, or any public API
- Tests: new `tests/test_sanitize.py` covering each vector; update `test_extractor.py` to cover sanitization integration
