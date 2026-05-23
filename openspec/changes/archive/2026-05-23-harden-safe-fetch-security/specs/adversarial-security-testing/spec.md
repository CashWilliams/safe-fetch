## ADDED Requirements

### Requirement: SSRF bypass corpus
The test suite SHALL include an SSRF bypass corpus covering userinfo, fragments, encoded hosts, backslashes, decimal/octal IPv4, IPv4-mapped IPv6, local aliases, mixed A/AAAA answers, redirect targets, and metadata endpoints.

#### Scenario: Corpus cases are rejected
- **WHEN** the SSRF bypass corpus is executed
- **THEN** every disallowed case raises the expected URL, host policy, or SSRF exception before unsafe connection

### Requirement: DNS rebinding simulation tests
The test suite SHALL simulate DNS answers changing between validation and connection.

#### Scenario: Rebinding simulation fails closed
- **WHEN** the simulated resolver returns a public address first and a private address at connection time
- **THEN** safe-fetch blocks the request

### Requirement: Property-based URL parser tests
The test suite SHALL use property-based tests or equivalent generated cases to verify URL canonicalization security invariants.

#### Scenario: Rejected URLs do not reach network layer
- **WHEN** generated invalid URLs are passed to safe-fetch
- **THEN** no DNS resolution or HTTP request is attempted

### Requirement: Prompt-injection fixture corpus
The test suite SHALL include direct, indirect, Unicode-obfuscated, typoglycemia, encoded, Markdown, HTML, fake tool-call, and exfiltration prompt-injection fixtures.

#### Scenario: Fixture corpus produces expected findings
- **WHEN** the prompt-injection corpus is scanned
- **THEN** expected findings, redactions, and risk levels are asserted

### Requirement: Hidden-content fixture corpus
The test suite SHALL include hidden HTML, CSS, SVG, comments, zero-size, offscreen, and rendered/text mismatch fixtures.

#### Scenario: Hidden fixture content is removed or flagged
- **WHEN** hidden-content fixtures are extracted
- **THEN** hidden payloads are absent from safe output or recorded as safety events

### Requirement: Warning-free CI
The default test command SHALL run with warnings treated as errors for the project test suite.

#### Scenario: Runtime warning fails tests
- **WHEN** a coroutine warning, resource warning, or deprecation warning is emitted by safe-fetch code during tests
- **THEN** CI fails
