## ADDED Requirements

### Requirement: Parallel .md URL probe
When the primary fetch returns an HTML response, the pipeline SHALL simultaneously request the same URL with `.md` appended to its path. If that probe returns HTTP 200 with `Content-Type: text/markdown` or `text/plain`, the probe content SHALL be used as the result with `extraction_method="md-probe"`. The probe SHALL run concurrently with the primary fetch using `asyncio.gather` so that a probe miss adds no latency. If the original URL already ends in `.md`, the probe SHALL be skipped.

#### Scenario: .md probe succeeds and is used
- **WHEN** `https://example.com/docs/page` is fetched and the server returns HTML, and `https://example.com/docs/page.md` returns HTTP 200 with `Content-Type: text/markdown`
- **THEN** the result uses the `.md` response content and `extraction_method="md-probe"`

#### Scenario: .md probe returns 404 — falls through to HTML extraction
- **WHEN** `https://example.com/docs/page.md` returns HTTP 404 or any non-200 status
- **THEN** the pipeline continues to trafilatura/readability extraction without error

#### Scenario: .md probe returns HTML — rejected
- **WHEN** `https://example.com/docs/page.md` returns HTTP 200 with `Content-Type: text/html`
- **THEN** the probe result is discarded and the pipeline falls through to HTML extraction

#### Scenario: .md probe error is swallowed
- **WHEN** the probe request raises a network exception (timeout, connection error)
- **THEN** the pipeline continues to HTML extraction; no error is surfaced to the caller

#### Scenario: URL already ends in .md — probe skipped
- **WHEN** the requested URL is `https://example.com/README.md`
- **THEN** no secondary probe request is made

#### Scenario: .md probe does not fire for non-HTML responses
- **WHEN** the server already returned `text/markdown` via content negotiation
- **THEN** no `.md` probe request is made

## REMOVED Requirements

### Requirement: llms.txt discovery
**Reason:** `llms.txt` is a site-level index document, not page-level content. Returning it in response to a page-specific URL fetch produces misleading results. The `.md` probe is a direct replacement that actually retrieves content for the requested page.
**Migration:** Callers relying on `extraction_method="llms-txt"` should update to handle `"md-probe"` instead. The `llms-txt` Python package dependency is removed.
