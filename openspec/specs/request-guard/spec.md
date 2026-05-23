## ADDED Requirements

### Requirement: Secret detection in URLs
The request guard SHALL scan URL query parameter values for high-entropy strings and known secret patterns before any network request is made. Detection uses `detect-secrets` detectors including `AWSKeyDetector`, `GitHubTokenDetector`, `KeywordDetector`, and `HexHighEntropyString`/`Base64HighEntropyString` entropy scanners.

#### Scenario: API key in query parameter is blocked under STRICT policy
- **WHEN** `safe_fetch("https://api.example.com/data?api_key=AKIAIOSFODNN7EXAMPLE")` is called with `request_policy=STRICT`
- **THEN** a `SecretLeakError` is raised before any network connection is made, with a finding indicating the parameter name and detector type

#### Scenario: Secret in query parameter warns under WARN policy
- **WHEN** `safe_fetch("https://api.example.com/data?token=ghp_abc123xyz")` is called with `request_policy=WARN`
- **THEN** a warning is logged with the finding details, the request proceeds, and the result includes a `request_findings` list with the detected secret

#### Scenario: Clean URL passes without findings
- **WHEN** `safe_fetch("https://example.com/page")` is called with no secrets in the URL
- **THEN** no findings are produced and the request proceeds normally

### Requirement: PII detection in URLs
The request guard SHALL scan URL query parameter values for common PII patterns — email addresses, phone numbers (E.164 and common formats), credit card numbers (Luhn-valid 13–19 digit sequences), and US Social Security Numbers — using regex recognizers.

#### Scenario: Email address in query parameter is detected
- **WHEN** `safe_fetch("https://example.com/lookup?email=user@example.com")` is called with `request_policy=STRICT`
- **THEN** a `PIILeakError` is raised before any network connection is made

#### Scenario: Credit card number in query parameter is detected
- **WHEN** a URL contains a Luhn-valid 16-digit sequence in a query parameter
- **THEN** a PII finding of type `credit_card` is produced

### Requirement: Secret detection in request headers
The request guard SHALL scan HTTP request header values for secrets and PII using the same detectors as URL scanning. The `Authorization` header value SHALL always be scanned.

#### Scenario: Bearer token in Authorization header is flagged
- **WHEN** `safe_fetch(url, headers={"Authorization": "Bearer ghp_abc123xyz"})` is called with `request_policy=STRICT`
- **THEN** a `SecretLeakError` is raised — bearer tokens are not exempted even when in Authorization header, since the content may be an unintentionally exposed secret rather than a legitimate credential

#### Scenario: Standard non-secret headers pass through
- **WHEN** headers contain only `User-Agent`, `Accept`, and `Content-Type`
- **THEN** no findings are produced

### Requirement: SSRF and private IP blocking
The request guard SHALL block requests to private IP ranges (RFC 1918), loopback addresses, link-local addresses, and metadata service IPs (e.g. 169.254.169.254) regardless of policy mode. SSRF blocking is NOT subject to `WARN` or `PERMISSIVE` policy — it is always enforced.

#### Scenario: Request to private IP is always blocked
- **WHEN** `safe_fetch("http://192.168.1.1/admin")` is called with any policy mode including `PERMISSIVE`
- **THEN** an `SSRFBlockedError` is raised before any network connection is made

#### Scenario: Request to AWS metadata endpoint is blocked
- **WHEN** `safe_fetch("http://169.254.169.254/latest/meta-data/")` is called
- **THEN** an `SSRFBlockedError` is raised

#### Scenario: DNS-resolved private IP is blocked
- **WHEN** a hostname resolves to a private IP address
- **THEN** the connection is refused with an `SSRFBlockedError` after DNS resolution but before connection

### Requirement: URL scheme validation
The request guard SHALL only allow `https://` and `http://` schemes. All other schemes (`file://`, `ftp://`, `data:`, etc.) SHALL be rejected.

#### Scenario: File scheme is rejected
- **WHEN** `safe_fetch("file:///etc/passwd")` is called
- **THEN** an `InvalidSchemeError` is raised immediately
