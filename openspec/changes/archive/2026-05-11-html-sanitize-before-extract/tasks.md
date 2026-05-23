## 1. Implement sanitize_html()

- [x] 1.1 Add `sanitize_html(html: str) -> str` to `safe_fetch/_extractor.py` using `BeautifulSoup(html, "lxml")`
- [x] 1.2 Strip elements with `display:none` inline style (normalize whitespace, lowercase, substring match)
- [x] 1.3 Strip elements with `visibility:hidden` inline style
- [x] 1.4 Strip elements with `opacity:0` inline style
- [x] 1.5 Strip elements with `font-size:0` or `font-size:0px` inline style
- [x] 1.6 Strip elements with off-screen positioning: `position:absolute` or `position:fixed` combined with `left:-` or `top:-` (negative coordinate)
- [x] 1.7 Strip elements with the `hidden` HTML attribute
- [x] 1.8 Strip all `<script>` tags (any type)
- [x] 1.9 Strip all `<template>` and `<noscript>` elements
- [x] 1.10 Strip all HTML comment nodes (`Comment` type from `bs4.element`)
- [x] 1.11 Return `str(soup)` after all mutations

## 2. Wire into extract()

- [x] 2.1 Call `sanitize_html(html)` at the top of `extract()` and pass the result to both `_try_trafilatura` and `_try_readability_markdownify`

## 3. Tests

- [x] 3.1 Test `display:none` element is stripped (text absent from sanitized HTML)
- [x] 3.2 Test `visibility:hidden` element is stripped
- [x] 3.3 Test `opacity:0` element is stripped
- [x] 3.4 Test `font-size:0px` element is stripped
- [x] 3.5 Test off-screen positioned element (`position:absolute;left:-9999px`) is stripped
- [x] 3.6 Test multi-property style containing `display:none` is stripped
- [x] 3.7 Test visible element with unrelated style is preserved
- [x] 3.8 Test entire subtree of hidden element is removed (children absent)
- [x] 3.9 Test HTML comment is stripped
- [x] 3.10 Test `hidden` attribute element is stripped
- [x] 3.11 Test `<script type="text/plain">` is stripped
- [x] 3.12 Test `<template>` element is stripped
- [x] 3.13 Test `<noscript>` element is stripped
- [x] 3.14 Integration test: `extract()` with a `display:none` injection div returns clean content without injection payload
- [x] 3.15 Integration test: HTML fixture matching the trixie.html pattern (display:none with `[CONFIDENT_MODE_OVERRIDE]`) is blocked end-to-end
