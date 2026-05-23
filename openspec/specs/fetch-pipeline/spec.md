## Purpose
Define the HTTP fetch, markdown negotiation, extraction fallback, timeout, and redirect behavior used by `safe_fetch()`.

## Requirements

### Requirement: Markdown content negotiation
The fetch pipeline SHALL attempt to retrieve content as markdown by including `Accept: text/markdown, text/plain;q=0.9, text/html;q=0.8` in the request headers. If the server responds with `Content-Type: text/markdown` or `text/plain`, the response body is used directly without HTML extraction.

#### Scenario: Markdown response is used directly
- **WHEN** the server responds with `Content-Type: text/markdown`
- **THEN** the response body is returned as-is (after response guard scanning), with `extraction_method="content-negotiation"` in the result

#### Scenario: HTML response falls through to extraction
- **WHEN** the server responds with `Content-Type: text/html`
- **THEN** the pipeline proceeds to the .md probe and HTML extraction steps

### Requirement: Parallel .md URL probe
When the primary fetch returns an HTML response, the pipeline SHALL request the same URL with `.md` appended to its path while HTML extraction runs. If that probe returns HTTP 200 with `Content-Type: text/markdown` or `text/plain`, the probe content SHALL be used as the result with `extraction_method="md-probe"`. The probe SHALL run concurrently with HTML extraction using `asyncio.gather` so that a probe miss adds no extra latency beyond extraction work. If the original URL already ends in `.md`, the probe SHALL be skipped.

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

### Requirement: Primary HTML extraction via trafilatura
When content negotiation and the .md probe both fail, the fetch pipeline SHALL use `trafilatura` to extract main content from the HTML and output it as markdown.

#### Scenario: trafilatura extracts article content
- **WHEN** a news article or documentation page is fetched
- **THEN** `trafilatura.extract(html, output_format="markdown")` produces clean content, `extraction_method="trafilatura"`

#### Scenario: trafilatura returns None — falls through to fallback
- **WHEN** trafilatura returns `None` (e.g., page has no extractable main content)
- **THEN** the pipeline proceeds to the readability + markdownify fallback

### Requirement: Fallback extraction via readability-lxml and markdownify
When trafilatura fails to extract content, the fetch pipeline SHALL use `readability-lxml` to isolate the main content block and `markdownify` to convert it to markdown.

#### Scenario: Fallback produces markdown from HTML
- **WHEN** trafilatura returned None and the page has a main content block
- **THEN** `readability-lxml` extracts the article HTML and `markdownify` converts it, with `extraction_method="readability+markdownify"`

#### Scenario: Both extraction methods fail
- **WHEN** both trafilatura and readability-lxml fail to extract meaningful content
- **THEN** an `ExtractionFailedError` is raised with the HTTP status and URL

### Requirement: Request timeouts
The fetch pipeline SHALL enforce configurable timeouts with defaults of 10 seconds for connection and 30 seconds for total response. Timeouts raise `FetchTimeoutError`.

#### Scenario: Connection timeout raises FetchTimeoutError
- **WHEN** the server does not accept the connection within the connect timeout
- **THEN** a `FetchTimeoutError` is raised with `phase="connect"`

#### Scenario: Read timeout raises FetchTimeoutError
- **WHEN** the server accepts the connection but does not complete the response within the read timeout
- **THEN** a `FetchTimeoutError` is raised with `phase="read"`

### Requirement: Redirect following with limit
The fetch pipeline SHALL follow HTTP redirects up to a maximum of 5 hops. Each redirect target SHALL be re-validated by the request guard (SSRF check, scheme check) before following. If the redirect limit is exceeded, `RedirectLimitError` SHALL be raised.

#### Scenario: Redirect to private IP is blocked
- **WHEN** an initial request to a public URL is redirected to a private IP (open redirect attack)
- **THEN** the request guard blocks the redirect with `SSRFBlockedError`

#### Scenario: Normal redirect chain is followed
- **WHEN** a URL redirects 1–5 times to public HTTPS URLs
- **THEN** the final response is returned normally

#### Scenario: Redirect limit exceeded
- **WHEN** a URL redirects more than 5 times
- **THEN** `RedirectLimitError` is raised
