## Context

`extract()` in `_extractor.py` passes raw HTML directly to trafilatura and readability. Neither extractor filters CSS-hidden content — trafilatura's main-content heuristics operate on text density and structural signals, not CSS visibility. Empirical research (Unit 42, 2025; arXiv 2604.27202) documents ~70% of in-the-wild prompt injections appear in non-rendered HTML. The `https://cashwilliams.com/trixie/` page demonstrates a live `<div style="display:none">` carrying a full injection payload that passes through safe-fetch today.

`BeautifulSoup` is already a transitive dependency via `readability-lxml`. We parse once, remove all invisible/non-rendered nodes, then re-serialize to a clean HTML string for extractors.

## Goals / Non-Goals

**Goals:**
- Remove CSS inline style vectors: `display:none`, `visibility:hidden`, `opacity:0`, `font-size:0/0px`, and off-screen absolute/fixed positioning (`left:-Npx` or `top:-Npx`)
- Remove HTML structural vectors: comments, `hidden` attribute, `<script>` (all types), `<template>`, `<noscript>`
- Keep sanitization a single `str → str` function in `_extractor.py`, called once at the top of `extract()`
- Zero new runtime dependencies

**Non-Goals:**
- CSS class-based hiding (`.hidden`, `.sr-only`) — requires stylesheet resolution, not feasible without executing CSS
- JavaScript-injected hiding (`element.style.display = 'none'` set at runtime) — safe-fetch doesn't execute JS
- `color:transparent` / white-on-white text — requires computed style context to detect reliably
- `<script type="application/ld+json">` structured data — harmless metadata, not rendered as visible content to users but also not an injection vector in practice

## Decisions

### 1. BeautifulSoup with `lxml` parser

**Decision:** `BeautifulSoup(html, "lxml")` for parse + mutate + re-serialize.

**Rationale:** `lxml` is already installed via `readability-lxml`. Consistent with the readability fallback path. More spec-compliant than `html.parser` on malformed HTML — exactly the kind we see in the wild from adversarially constructed pages.

**Alternatives considered:** regex stripping — unreliable on nested/malformed HTML; `lxml.etree` directly — more verbose for comment and attribute traversal.

### 2. Style matching: normalize then substring check

**Decision:** For each element with a `style` attribute, strip whitespace around `:` and `;`, lowercase, then check for known substrings. Decompose elements that match.

**Rationale:** Inline styles may contain multiple properties (`"color:red; display:none; margin:0"`). After normalization `display:none` is unambiguous as a substring. Handles both `display:none` and `display: none` (with spaces). No CSS parser needed.

**Off-screen positioning** requires a two-part check: style contains `position:absolute` or `position:fixed`, AND style contains a regex match for `left:-\d` or `top:-\d` (negative coordinate). Both conditions required to avoid false positives on legitimate fixed headers.

### 3. Structural elements: tag name + attribute removal

**Decision:**
- `hidden` attribute: any tag with `tag.has_attr("hidden")` → decompose
- `<script>` of any type: `soup.find_all("script")` → decompose all
- `<template>`, `<noscript>`: `soup.find_all(["template", "noscript"])` → decompose all
- Comments: `soup.find_all(string=lambda t: isinstance(t, Comment))` → extract (remove)

**Rationale:** These elements are never rendered as visible page content to users. `<script type="text/plain">` is a documented injection vector (content not executed but present in DOM). `<template>` content is inert by spec. `<noscript>` is visible only when JS is disabled — in safe-fetch's context (no JS execution) it would be rendered, so removing it is conservative but correct.

**Note on `<script>`:** trafilatura already discards script tags in most cases, but readability's fallback path does not consistently. Removing explicitly is belt-and-suspenders.

### 4. Decompose entire subtrees

**Decision:** `tag.decompose()` removes element and all children.

**Rationale:** An injection payload inside `<div style="display:none">` may be further wrapped in `<p>`, `<span>`, `<ol>` children. Removing only the outer element's own text node while leaving children would be incomplete. Full subtree removal is correct.

## Risks / Trade-offs

- **Legitimate off-screen accessible text removed** → Some screen-reader-only patterns use `position:absolute; left:-9999px`. This content is intentionally not part of the visible page text and safe-fetch's goal is to produce content equivalent to what a human reader sees.
- **`<noscript>` removal on JS-free pages** → A page may provide meaningful fallback content in `<noscript>`. Accepted: the primary fetch path assumes JS-capable rendering is the norm.
- **Performance** → One BeautifulSoup parse per HTML fetch. Benchmarks on typical news/docs pages show < 20ms overhead. Acceptable given the security benefit.
- **Attacker switches to CSS class hiding** → Requires stylesheet execution; not feasible to block without full CSS evaluation. Mitigated by existing response guard injection detection as defence-in-depth.
