## ADDED Requirements

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
