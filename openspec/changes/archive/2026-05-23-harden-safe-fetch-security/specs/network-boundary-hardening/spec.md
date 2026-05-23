## ADDED Requirements

### Requirement: Canonical URL validation
safe-fetch SHALL canonicalize and validate every caller-provided, redirect, and probe URL before any network access. Canonicalization SHALL reject non-HTTP(S) schemes, empty hosts, invalid ports, URL userinfo, fragments, backslashes, ASCII control characters, malformed IPv6 brackets, ambiguous IP encodings, and hostnames whose IDNA or NFKC processing changes their security meaning.

#### Scenario: URL credentials are rejected
- **WHEN** `safe_fetch("https://user:pass@example.com/")` is called
- **THEN** `InvalidURLError` is raised before DNS resolution or connection

#### Scenario: Fragment is rejected
- **WHEN** `safe_fetch("https://example.com/page#token=abc")` is called
- **THEN** `InvalidURLError` is raised before DNS resolution or connection

#### Scenario: Ambiguous local address is rejected
- **WHEN** a URL host encodes loopback or private IP using decimal, octal, IPv4-mapped IPv6, or equivalent ambiguous forms
- **THEN** the URL is blocked before connection

### Requirement: Rebinding-safe DNS and connection validation
safe-fetch SHALL validate resolved IP addresses immediately before connection and SHALL NOT rely solely on a preflight DNS lookup. Each resolved A or AAAA address SHALL be checked against network policy before a socket connection is attempted.

#### Scenario: DNS rebinding is blocked
- **WHEN** DNS validation initially observes a public address but the connect-time resolution returns a private address
- **THEN** the request is blocked with `SSRFBlockedError`

#### Scenario: Mixed DNS answers are blocked
- **WHEN** a hostname resolves to both public and private addresses
- **THEN** the request is blocked unless configuration explicitly allows the private target

### Requirement: Globally-routable default network policy
safe-fetch SHALL allow only globally routable destination addresses by default. Private, loopback, link-local, multicast, unspecified, reserved, documentation, metadata, and local-name targets SHALL be blocked unless explicitly allowed by configuration.

#### Scenario: Documentation range is blocked
- **WHEN** a URL resolves to `192.0.2.1`
- **THEN** `SSRFBlockedError` is raised

#### Scenario: localhost alias is blocked
- **WHEN** a URL uses `localhost`, `*.localhost`, `.local`, or equivalent local-name host
- **THEN** `SSRFBlockedError` is raised

### Requirement: Host and CIDR policy controls
`SafeFetchConfig` SHALL support host allowlists, host suffix allowlists, blocked hosts, blocked CIDRs, and explicitly allowed CIDRs. Deny rules SHALL take precedence over allow rules.

#### Scenario: Host allowlist blocks unknown host
- **WHEN** `allowed_hosts={"docs.example.com"}` and `safe_fetch("https://blog.example.com/")` is called
- **THEN** `HostPolicyError` is raised before connection

#### Scenario: Deny rule wins over allow suffix
- **WHEN** `allowed_host_suffixes={".example.com"}` and `blocked_hosts={"evil.example.com"}`
- **THEN** `safe_fetch("https://evil.example.com/")` raises `HostPolicyError`

### Requirement: HTTPS policy
safe-fetch SHALL support `allow_http: bool` and SHALL reject `http://` URLs when `allow_http` is false.

#### Scenario: HTTP blocked by strict preset
- **WHEN** strict configuration has `allow_http=False` and `safe_fetch("http://example.com/")` is called
- **THEN** `InvalidSchemeError` or `InvalidURLError` is raised before connection

### Requirement: Sensitive request surface scanning
The request guard SHALL scan URL path segments, query keys, query values, URL userinfo if present before rejection reporting, and outgoing headers for secrets and PII. Findings SHALL store redacted snippets and stable hashes, not raw secret values.

#### Scenario: Secret in path is blocked
- **WHEN** a URL path contains a GitHub token
- **THEN** `SecretLeakError` is raised under strict leak policy before DNS resolution

#### Scenario: Finding snippet is redacted
- **WHEN** a request secret is detected
- **THEN** the resulting `RequestFinding.snippet` does not contain the raw secret
