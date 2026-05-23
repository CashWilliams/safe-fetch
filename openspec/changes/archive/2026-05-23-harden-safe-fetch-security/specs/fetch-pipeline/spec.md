## ADDED Requirements

### Requirement: Rebinding-safe fetch transport
The fetch pipeline SHALL use network-boundary validation at connection time for primary requests, redirects, and `.md` probes.

#### Scenario: Connect-time private IP is blocked
- **WHEN** connect-time resolution returns a private IP for an otherwise valid public hostname
- **THEN** the fetch pipeline raises `SSRFBlockedError`

### Requirement: Resource-limited streaming
The fetch pipeline SHALL stream response bodies while enforcing `max_response_bytes` and content-type policy before extraction.

#### Scenario: Stream stops at byte limit
- **WHEN** streamed response bytes exceed the configured maximum
- **THEN** the client stops reading and raises `ResponseTooLargeError`

### Requirement: Total timeout wraps full fetch
The fetch pipeline SHALL apply `total_timeout` to the complete fetch operation including redirects, probe, extraction, and response guard work.

#### Scenario: Slow extraction is timed out
- **WHEN** HTML extraction causes the operation to exceed `total_timeout`
- **THEN** `FetchTimeoutError` is raised with `phase="total"`

### Requirement: HTTP status and content type enforcement
The fetch pipeline SHALL reject disallowed HTTP statuses and content types before extraction or response scanning.

#### Scenario: Unsupported content type fails early
- **WHEN** a response has `Content-Type: image/png`
- **THEN** `UnsupportedContentTypeError` is raised before body extraction
