## ADDED Requirements

### Requirement: Canonical request target validation
The request guard SHALL validate canonical URL targets using the `network-boundary-hardening` capability before DNS resolution or HTTP connection.

#### Scenario: Unsafe canonical URL blocks before scanning proceeds to network
- **WHEN** a URL contains userinfo, a fragment, a control character, or an ambiguous local host encoding
- **THEN** request guard raises the appropriate URL or host policy error without attempting DNS resolution

### Requirement: Expanded request leak scanning
The request guard SHALL scan URL path segments, query parameter names, query parameter values, URL credentials when present before rejection reporting, and header values for secrets and PII.

#### Scenario: Secret in query key is detected
- **WHEN** a URL contains a query key that includes an API key or token value
- **THEN** a secret finding is produced and STRICT policy raises `SecretLeakError`

#### Scenario: PII in path is detected
- **WHEN** a URL path contains an email address or Luhn-valid credit card number
- **THEN** a PII finding is produced and STRICT policy raises `PIILeakError`

### Requirement: Redacted request findings
Request findings SHALL NOT store raw secret or PII values in snippets, logs, exception messages, wrapped content, or CLI JSON. Findings SHALL include location, detector, kind, redacted snippet, and optional stable hash.

#### Scenario: Exception message avoids raw secret
- **WHEN** `SecretLeakError` is raised for a token in the URL
- **THEN** the exception message and finding snippet do not contain the raw token
