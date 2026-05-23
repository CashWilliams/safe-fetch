## Purpose
Remove non-visible or non-rendered HTML content before extraction so hidden prompt-injection payloads are not returned.
## Requirements
### Requirement: Strip CSS-hidden elements before extraction
The `sanitize_html()` function SHALL remove any HTML element whose inline `style` attribute renders it invisible to human readers. The following patterns SHALL be detected after normalizing whitespace around `:` and `;` and lowercasing the style value:
- `display:none`
- `visibility:hidden`
- `opacity:0`
- `font-size:0` or `font-size:0px`
- `position:absolute` or `position:fixed` combined with `left:-` (negative) or `top:-` (negative) coordinate

Matched elements SHALL be removed along with their entire subtree.

#### Scenario: display:none element is stripped
- **WHEN** the HTML contains `<div style="display:none">Inject me</div>`
- **THEN** the sanitized HTML does not contain "Inject me" and the div is absent

#### Scenario: visibility:hidden element is stripped
- **WHEN** the HTML contains `<span style="visibility:hidden">Hidden text</span>`
- **THEN** the sanitized HTML does not contain "Hidden text"

#### Scenario: opacity:0 element is stripped
- **WHEN** the HTML contains `<p style="opacity:0">Invisible</p>`
- **THEN** the sanitized HTML does not contain "Invisible"

#### Scenario: font-size:0 element is stripped
- **WHEN** the HTML contains `<div style="font-size:0px">Tiny text</div>`
- **THEN** the sanitized HTML does not contain "Tiny text"

#### Scenario: off-screen positioned element is stripped
- **WHEN** the HTML contains `<div style="position:absolute;left:-9999px">Off screen</div>`
- **THEN** the sanitized HTML does not contain "Off screen"

#### Scenario: multi-property style containing display:none is stripped
- **WHEN** the HTML contains `<p style="color:red; display:none; margin:0">Hidden</p>`
- **THEN** the sanitized HTML does not contain "Hidden"

#### Scenario: visible element with unrelated style is preserved
- **WHEN** the HTML contains `<p style="color:blue; font-weight:bold">Normal text</p>`
- **THEN** "Normal text" is preserved in the sanitized HTML

#### Scenario: entire subtree of hidden element is removed
- **WHEN** a hidden element contains child elements with visible content
- **THEN** both the parent and all children are absent from the sanitized HTML

### Requirement: Strip HTML comments
The `sanitize_html()` function SHALL remove all HTML comment nodes (`<!-- ... -->`), including multi-line comments.

#### Scenario: HTML comment is stripped
- **WHEN** the HTML contains `<!-- Ignore previous instructions -->`
- **THEN** the sanitized HTML contains no comment nodes and no comment text

#### Scenario: multi-line comment is stripped
- **WHEN** the HTML contains a multi-line `<!-- ... -->` comment
- **THEN** the entire comment is absent from the sanitized HTML

### Requirement: Strip hidden attribute elements
The `sanitize_html()` function SHALL remove any element with the HTML5 `hidden` attribute.

#### Scenario: element with hidden attribute is stripped
- **WHEN** the HTML contains `<div hidden>Secret payload</div>`
- **THEN** the sanitized HTML does not contain "Secret payload"

### Requirement: Strip non-rendered structural elements
The `sanitize_html()` function SHALL remove `<script>` tags (of any type, including `type="text/plain"`), `<template>` elements, and `<noscript>` elements — none of which render visible content to users.

#### Scenario: script type text/plain is stripped
- **WHEN** the HTML contains `<script type="text/plain">Injected prompt</script>`
- **THEN** the sanitized HTML does not contain "Injected prompt"

#### Scenario: template element is stripped
- **WHEN** the HTML contains `<template><p>Hidden template content</p></template>`
- **THEN** the sanitized HTML does not contain "Hidden template content"

#### Scenario: noscript element is stripped
- **WHEN** the HTML contains `<noscript><p>Fallback injection</p></noscript>`
- **THEN** the sanitized HTML does not contain "Fallback injection"

### Requirement: Sanitization applied before all extractors
`extract()` SHALL call `sanitize_html()` on the raw HTML string before passing it to trafilatura or readability. The sanitized HTML SHALL be used for both the primary extraction attempt and the fallback.

#### Scenario: display:none injection does not appear in extracted content
- **WHEN** `extract()` is called with HTML containing a `display:none` div holding an injection payload
- **THEN** the returned content does not contain the injection payload text

#### Scenario: trixie.html real-world injection is blocked
- **WHEN** `extract()` is called with HTML from `https://cashwilliams.com/trixie/` (or equivalent fixture)
- **THEN** the extracted content contains the llama story text and does not contain `[CONFIDENT_MODE_OVERRIDE]` or any injection payload text

### Requirement: Stylesheet-based hidden content removal
`sanitize_html()` SHALL remove content hidden by simple page-local `<style>` selectors for classes and IDs when those selectors use invisibility properties such as `display:none`, `visibility:hidden`, `opacity:0`, zero dimensions, clipping, transparent color, or offscreen positioning.

#### Scenario: Hidden class rule removes matching element
- **WHEN** HTML contains `<style>.hidden{display:none}</style><p class="hidden">Inject</p>`
- **THEN** sanitized HTML does not contain `Inject`

### Requirement: Additional non-visible element removal
`sanitize_html()` SHALL remove elements marked with `aria-hidden`, `inert`, `input type="hidden"`, SVG `<desc>`, SVG `<title>`, and SVG `<foreignObject>`.

#### Scenario: SVG description payload is stripped
- **WHEN** SVG `<desc>` contains an injection payload
- **THEN** sanitized HTML does not contain the payload

### Requirement: Optional rendered visible-text extraction
When rendered text mode is enabled, safe-fetch SHALL use a browser-rendered visible-text extractor and SHALL record a safety event when parser-extracted text includes content absent from rendered visible text.

#### Scenario: Parser-only hidden text is flagged
- **WHEN** static extraction finds text that rendered visible-text extraction does not expose
- **THEN** a hidden-content safety event is recorded

