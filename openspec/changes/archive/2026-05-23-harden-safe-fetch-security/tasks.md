## 1. API and Data Model Foundation

- [x] 1.1 Add new exception classes: `InvalidURLError`, `HostPolicyError`, `ResponseTooLargeError`, `UnsupportedContentTypeError`, `HTTPStatusError`, and `ClassifierError`
- [x] 1.2 Extend `SafeFetchConfig` with network policy, resource limit, content policy, redaction, classifier, and safe Markdown fields
- [x] 1.3 Add `SafeFetchConfig.agent_default()`, `SafeFetchConfig.strict_enterprise()`, and `SafeFetchConfig.permissive_research()` preset constructors
- [x] 1.4 Add metadata dataclasses: `FetchMetadata`, `ContentIntegrity`, `SafetyEvent`, and `RiskAssessment`
- [x] 1.5 Extend `SafeFetchResult` with `safe_content`, `metadata`, `integrity`, `safety_events`, and `risk` fields while preserving existing fields
- [x] 1.6 Export new public exceptions and metadata dataclasses from `safe_fetch.__init__`
- [x] 1.7 Add compatibility tests for existing imports and result fields

## 2. Canonical URL and Network Boundary

- [x] 2.1 Create `_url.py` with `CanonicalURL` and `canonicalize_url(raw_url, config)`
- [x] 2.2 Reject unsafe schemes, empty hosts, invalid ports, fragments, userinfo, backslashes, control characters, malformed IPv6, and ambiguous IP encodings
- [x] 2.3 Implement IDNA/NFKC hostname validation and local-name blocking for `localhost`, `*.localhost`, `.local`, and equivalents
- [x] 2.4 Implement host allowlist, host suffix allowlist, blocked hosts, blocked CIDRs, and allowed CIDRs with deny precedence
- [x] 2.5 Change request guard, fetch pipeline, redirects, `.md` probe construction, marker source metadata, and provenance to use `CanonicalURL`
- [x] 2.6 Implement connect-time IP validation or integrate an audited rebinding-safe `httpx` transport adapter
- [x] 2.7 Use globally-routable-address allow-by-default logic for resolved IP addresses
- [x] 2.8 Add unit tests for canonicalization rejection and accepted normalized URLs
- [x] 2.9 Add tests proving rejected URLs do not call DNS or `httpx`
- [x] 2.10 Add DNS rebinding simulation tests and mixed public/private DNS answer tests

## 3. Request Leak Scanning

- [x] 3.1 Extend request scanning to URL path segments, query parameter names, query values, URL credentials before rejection reporting, and headers
- [x] 3.2 Add redaction utility for finding snippets and exception/log messages
- [x] 3.3 Add stable hash field support for request findings without storing raw secrets
- [x] 3.4 Ensure strict leak findings block before DNS or HTTP work
- [x] 3.5 Add tests for secrets and PII in paths, query keys, query values, credentials, and headers
- [x] 3.6 Add tests that request findings, logs, exceptions, CLI JSON, and marker source attributes do not contain raw secret values

## 4. Fetch Resource Controls

- [x] 4.1 Stream response bodies instead of reading unbounded `response.text`
- [x] 4.2 Enforce `max_response_bytes` during streaming and raise `ResponseTooLargeError`
- [x] 4.3 Enforce `total_timeout` around the full fetch operation and map expiry to `FetchTimeoutError(phase="total")`
- [x] 4.4 Enforce HTTP status policy before extraction and raise `HTTPStatusError` for rejected statuses
- [x] 4.5 Enforce content-type allowlist before extraction and raise `UnsupportedContentTypeError`
- [x] 4.6 Apply canonical URL and network policy validation to redirects and `.md` probe URLs
- [x] 4.7 Enforce `max_redirects` from config instead of a hard-coded redirect limit
- [x] 4.8 Add extraction worker concurrency limiting around blocking extraction work
- [x] 4.9 Add tests for byte limit, total timeout, status rejection, content-type rejection, redirect/probe revalidation, and extraction worker limiting

## 5. Safe Markdown Output

- [x] 5.1 Create `_safe_markdown.py` with safe Markdown transformation entry point
- [x] 5.2 Neutralize Markdown images, reference images, raw HTML blocks, comments, embedded SVG, scripts, templates, noscript content, and suspicious autolinks
- [x] 5.3 Implement configurable link policy that preserves visible link text while neutralizing denied hrefs
- [x] 5.4 Wire safe Markdown transformation after response scanning and before boundary wrapping
- [x] 5.5 Populate `raw_content`, `safe_content`, and wrapped `content` according to config
- [x] 5.6 Record safety events for every Markdown neutralization
- [x] 5.7 Add tests for image exfiltration, raw HTML, comments, SVG, autolinks, reference links, and preservation of raw content

## 6. Response Guard Hardening

- [x] 6.1 Implement classifier timeout handling with `asyncio.wait_for` or equivalent
- [x] 6.2 Apply `classifier_failure_policy` with strict failure raising `ClassifierError`
- [x] 6.3 Expand injection pattern coverage for indirect injection, typoglycemia, encoded payloads, fake tool calls, instruction hierarchy markers, and exfiltration phrases
- [x] 6.4 Implement normalized-match redaction that redacts original content when detection only fires after Unicode normalization
- [x] 6.5 Implement `redaction_mode` values: `none`, `pattern`, `snippet`, `segment`, and `document`
- [x] 6.6 Record classifier, redaction, and response-guard policy safety events
- [x] 6.7 Add tests for classifier timeout/failure policies, normalized-only redaction, redaction modes, fake tool calls, typoglycemia, and encoded prompt-injection fixtures

## 7. HTML Sanitization and Rendered Text

- [x] 7.1 Extend inline style detection for zero width/height, clipping, transparent color, offscreen right/bottom, transform hiding, and related invisibility properties
- [x] 7.2 Parse simple page-local `<style>` rules for hidden class and ID selectors
- [x] 7.3 Remove `aria-hidden`, `inert`, `input type="hidden"`, SVG `<desc>`, SVG `<title>`, and SVG `<foreignObject>` content
- [x] 7.4 Record sanitizer removal events with category and approximate count
- [x] 7.5 Add optional rendered visible-text extraction behind the existing Playwright extra or a new optional extra
- [x] 7.6 Compare rendered visible text with parser-extracted text and record hidden-content delta events
- [x] 7.7 Add tests for stylesheet-hidden content, SVG payloads, additional hidden attributes/elements, and optional rendered-text mismatch behavior

## 8. Provenance, Integrity, and Risk

- [x] 8.1 Capture fetch metadata: final URL, redacted source URL, source host, status code, content type, content length, ETag, Last-Modified, redirect chain, fetched_at, and elapsed milliseconds
- [x] 8.2 Compute SHA-256 hashes for `raw_content` and `safe_content`
- [x] 8.3 Aggregate request findings, response findings, sanitizer removals, Markdown neutralizations, redirects, source policy, and classifier outcomes into `SafetyEvent` records
- [x] 8.4 Implement risk scoring with categorical levels and reason strings
- [x] 8.5 Add metadata and risk to CLI JSON output
- [x] 8.6 Add tests for redirect-chain metadata, hashes, safety events, risk reasons, and JSON serialization

## 9. CLI and Documentation

- [x] 9.1 Parse new `SAFE_FETCH_*` environment variables for limits, host/CIDR policy, content types, status policy, redaction mode, safe Markdown, classifier timeout, and classifier failure policy
- [x] 9.2 Add validation and error messages for malformed host lists, CIDRs, booleans, integers, floats, content types, and policy values
- [x] 9.3 Add documented exit codes for `InvalidURLError`, `HostPolicyError`, `ResponseTooLargeError`, `UnsupportedContentTypeError`, `HTTPStatusError`, and `ClassifierError`
- [x] 9.4 Update `--help` with new env vars, defaults, examples, and full exit code table
- [x] 9.5 Update README with threat model, residual risks, secure agent usage, safe Markdown behavior, metadata fields, and policy presets
- [x] 9.6 Add CLI tests for new env vars, invalid env values, new exit codes, and JSON metadata fields

## 10. Adversarial Security Test Suite

- [x] 10.1 Create `tests/security/` structure for SSRF, URL parsing, DNS, prompt-injection, hidden-content, Markdown, and fixtures
- [x] 10.2 Add SSRF bypass corpus covering userinfo, fragments, encoded hosts, backslashes, decimal/octal IPv4, IPv4-mapped IPv6, local aliases, mixed DNS answers, redirects, and metadata endpoints
- [x] 10.3 Add property-based URL tests for canonicalization invariants
- [x] 10.4 Add DNS rebinding and mixed-answer resolver fixtures
- [x] 10.5 Add prompt-injection fixtures for direct, indirect, Unicode-obfuscated, typoglycemia, encoded, Markdown, HTML, fake tool-call, and exfiltration attacks
- [x] 10.6 Add hidden-content fixtures for CSS, comments, SVG, zero-size, offscreen, and rendered/parser mismatch payloads
- [x] 10.7 Add Markdown exfiltration fixtures for image URLs, reference images, raw HTML, autolinks, and suspicious links
- [x] 10.8 Configure default test run or CI to treat project warnings as errors
- [x] 10.9 Add optional lint/type/security-audit commands if dependencies are available
- [x] 10.10 Run `openspec validate --all --strict` and the full Python test suite after implementation
