## ADDED Requirements

### Requirement: Security environment variables
The CLI SHALL expose new security controls exclusively through environment variables, including `SAFE_FETCH_MAX_RESPONSE_BYTES`, `SAFE_FETCH_TOTAL_TIMEOUT`, `SAFE_FETCH_MAX_REDIRECTS`, `SAFE_FETCH_ALLOW_HTTP`, `SAFE_FETCH_ALLOWED_HOSTS`, `SAFE_FETCH_ALLOWED_HOST_SUFFIXES`, `SAFE_FETCH_BLOCKED_HOSTS`, `SAFE_FETCH_BLOCKED_CIDRS`, `SAFE_FETCH_ALLOWED_CIDRS`, `SAFE_FETCH_ALLOWED_CONTENT_TYPES`, `SAFE_FETCH_HTTP_STATUS_POLICY`, `SAFE_FETCH_REDACTION_MODE`, `SAFE_FETCH_SAFE_MARKDOWN`, `SAFE_FETCH_CLASSIFIER_TIMEOUT`, and `SAFE_FETCH_CLASSIFIER_FAILURE_POLICY`.

#### Scenario: Byte limit env var is applied
- **WHEN** `SAFE_FETCH_MAX_RESPONSE_BYTES=1024 safe-fetch <url>` is run
- **THEN** the underlying config enforces a 1024-byte response limit

#### Scenario: Invalid CIDR exits with error
- **WHEN** `SAFE_FETCH_BLOCKED_CIDRS=not-a-cidr safe-fetch <url>` is run
- **THEN** an error is printed and the process exits 1

### Requirement: CLI exit codes for new errors
The CLI SHALL provide distinct exit codes for `InvalidURLError`, `HostPolicyError`, `ResponseTooLargeError`, `UnsupportedContentTypeError`, `HTTPStatusError`, and `ClassifierError`.

#### Scenario: Response too large has stable exit code
- **WHEN** fetching fails with `ResponseTooLargeError`
- **THEN** the CLI exits with the documented response-too-large exit code

### Requirement: JSON safety metadata
The CLI `--json` output SHALL include `safe_content`, `metadata`, `integrity`, `safety_events`, and `risk` fields on success.

#### Scenario: JSON includes risk assessment
- **WHEN** `safe-fetch --json <url>` succeeds
- **THEN** stdout contains a JSON object with `risk.level`, `risk.score`, and `risk.reasons`
