## ADDED Requirements

### Requirement: Maximum response size
The fetch pipeline SHALL enforce `max_response_bytes` while streaming the response body. If the limit is exceeded, fetching SHALL stop and `ResponseTooLargeError` SHALL be raised.

#### Scenario: Oversized response is blocked
- **WHEN** a server streams more bytes than `max_response_bytes`
- **THEN** safe-fetch stops reading and raises `ResponseTooLargeError`

### Requirement: Total fetch deadline
The fetch pipeline SHALL enforce `total_timeout` as a wall-clock deadline covering request guard work, redirects, primary fetch, `.md` probe, extraction, response guard work, and wrapping.

#### Scenario: Total deadline expires
- **WHEN** the full fetch operation exceeds `total_timeout`
- **THEN** `FetchTimeoutError` is raised with `phase="total"`

### Requirement: HTTP status policy
The fetch pipeline SHALL reject non-success HTTP status codes by default. Configurable status policy SHALL allow callers to opt into extracting error pages.

#### Scenario: 404 rejected by default
- **WHEN** the final response has status code `404`
- **THEN** `HTTPStatusError` is raised before extraction

#### Scenario: Permissive status policy extracts error page
- **WHEN** status policy allows `4xx` responses
- **THEN** extraction may proceed for an HTML `404` response

### Requirement: Content type allowlist
The fetch pipeline SHALL only process configured textual content types by default. Binary, archive, image, audio, video, and unknown content types SHALL be rejected unless explicitly allowed.

#### Scenario: Binary content is rejected
- **WHEN** the final response content type is `application/octet-stream`
- **THEN** `UnsupportedContentTypeError` is raised

### Requirement: Probe and redirect revalidation
The fetch pipeline SHALL canonicalize and validate every redirect target and every `.md` probe URL using the same network-boundary rules as the original URL.

#### Scenario: Probe target violates host policy
- **WHEN** constructing a `.md` probe would violate configured host or scheme policy
- **THEN** the probe is skipped or blocked according to the same policy without weakening the primary fetch

### Requirement: Extraction concurrency limit
The fetch pipeline SHALL limit concurrent blocking extraction work using a configurable worker limit.

#### Scenario: Worker limit reached
- **WHEN** more fetches need extraction than `max_extraction_workers`
- **THEN** additional extraction tasks wait instead of creating unbounded worker threads
