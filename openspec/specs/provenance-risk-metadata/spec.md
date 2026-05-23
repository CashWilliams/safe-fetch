# provenance-risk-metadata Specification

## Purpose
TBD - created by archiving change harden-safe-fetch-security. Update Purpose after archive.
## Requirements
### Requirement: Fetch provenance metadata
`SafeFetchResult` SHALL include structured fetch metadata with final URL, redacted source URL, source host, HTTP status, content type, content length when known, ETag, Last-Modified, redirect chain, fetched_at timestamp, and elapsed milliseconds.

#### Scenario: Redirect chain recorded
- **WHEN** a request follows two redirects before success
- **THEN** result metadata includes each redirect source and target URL in order

### Requirement: Content integrity metadata
`SafeFetchResult` SHALL include SHA-256 hashes for raw content and safe content.

#### Scenario: Hashes are populated
- **WHEN** safe-fetch succeeds
- **THEN** result integrity metadata contains `raw_content_sha256` and `safe_content_sha256`

### Requirement: Safety events
safe-fetch SHALL record sanitizer removals, Markdown neutralizations, redactions, classifier outcomes, policy decisions, and blocked optional probes as structured safety events.

#### Scenario: Hidden HTML removal is recorded
- **WHEN** sanitization removes a hidden element
- **THEN** result metadata includes a safety event describing the removal category

### Requirement: Risk assessment
safe-fetch SHALL compute a risk assessment with a numeric score, categorical level, and reason list from request findings, response findings, hidden content, redirects, HTTP downgrade, source policy, classifier results, and safe Markdown transformations.

#### Scenario: Injection finding raises risk
- **WHEN** response guard records a HIGH-confidence injection finding under WARN policy
- **THEN** result risk level is elevated and includes the finding as a reason

### Requirement: JSON serializable metadata
All provenance, integrity, safety event, and risk metadata SHALL be serializable through the CLI JSON output without custom user code.

#### Scenario: CLI JSON includes metadata
- **WHEN** `safe-fetch --json <url>` succeeds
- **THEN** stdout includes metadata, integrity, safety events, and risk assessment fields

