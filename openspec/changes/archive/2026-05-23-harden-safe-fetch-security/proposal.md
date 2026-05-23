## Why

safe-fetch is intended to let AI agents retrieve untrusted web content without leaking caller secrets, opening SSRF paths, or letting remote content masquerade as agent instructions. The current implementation covers the first layer of this threat model, but it still lacks hardened URL canonicalization, DNS rebinding protection, response size/status controls, safe Markdown handling, richer provenance, and a dedicated adversarial test corpus.

This change upgrades safe-fetch from a proof-of-concept guardrail into a defensible security boundary for common agent and RAG retrieval workflows, while documenting residual risks clearly.

## What Changes

- Add strict URL canonicalization and network-boundary controls:
  - Reject ambiguous or credential-bearing URLs before any network access.
  - Validate hostnames, IDNA/NFKC normalization, ports, fragments, userinfo, control characters, and path/query leak surfaces.
  - Add DNS rebinding-resistant connection behavior and globally-routable-address validation.
  - Add host and CIDR allow/block configuration.
- Add fetch resource controls:
  - Maximum response bytes, total wall-clock timeout, HTTP status policy, content-type allowlist, optional HTTPS-only mode, and redirect/probe validation.
- Add safe output modes:
  - Neutralize risky Markdown constructs such as images, raw HTML, comments, autolinks, and suspicious external links.
  - Fix normalized-detection versus original-content redaction mismatch.
  - Redact sensitive query/header material from boundary metadata by default.
- Expand HTML and response sanitization:
  - Cover CSS-hidden selectors, additional hidden attributes/elements, SVG metadata, zero-size/clip/offscreen styles, and optional rendered visible-text extraction.
- Add provenance, integrity, and risk metadata:
  - Content hashes, redirect chain, source host, content type/length, retrieval timestamps, sanitizer changes, risk score, and structured safety events.
- Add high-risk policy presets and fail-closed controls.
- Add a comprehensive adversarial testing suite:
  - SSRF bypass corpus, DNS rebinding simulation, property-based URL tests, prompt-injection fixtures, hidden-content fixtures, Markdown exfiltration fixtures, and warning-as-error CI.
- Update README and security guidance to emphasize instruction/data separation and residual risk.

## Capabilities

### New Capabilities
- `network-boundary-hardening`: URL canonicalization, SSRF bypass resistance, DNS rebinding protection, host/CIDR controls, HTTPS policy, and pre-network secret redaction.
- `fetch-resource-controls`: Response size limits, total deadline, content-type allowlist, HTTP status policy, redirect/probe validation, and extraction concurrency limits.
- `safe-markdown-output`: Safe Markdown transformation, dangerous Markdown/HTML neutralization, normalized redaction, and redacted source metadata.
- `provenance-risk-metadata`: Retrieval provenance, hashes, redirect chain, sanitizer events, safety findings, and aggregate risk scoring.
- `adversarial-security-testing`: Required security test corpus and CI verification for SSRF, prompt injection, hidden content, Markdown exfiltration, and parser fuzzing.

### Modified Capabilities
- `safe-fetch-api`: Add new config fields, result metadata fields, policy presets, redaction modes, and new structured errors.
- `request-guard`: Expand leak scanning beyond query values, require redacted findings, and integrate canonical URL validation.
- `fetch-pipeline`: Enforce resource limits, status/content-type policy, total timeout, redirect/probe revalidation, and rebinding-safe network access.
- `response-guard`: Add normalized redaction behavior, classifier timeout/failure policy, and expanded prompt-injection coverage.
- `html-sanitize`: Add broader hidden-content removal and optional rendered visible-text extraction.
- `content-boundary-markers`: Redact sensitive source URL attributes and support provenance-safe boundary metadata.
- `cli`: Add environment variables for new security controls and JSON metadata/error output.

## Impact

- Affected package modules:
  - `safe_fetch/_request_guard.py`
  - `safe_fetch/_fetch_pipeline.py`
  - `safe_fetch/_response_guard.py`
  - `safe_fetch/_extractor.py`
  - `safe_fetch/_marker.py`
  - `safe_fetch/_types.py`
  - `safe_fetch/_exceptions.py`
  - `safe_fetch/_cli.py`
  - `safe_fetch/__init__.py`
- New internal modules are expected for URL canonicalization, safe Markdown transformation, provenance/risk scoring, and DNS/transport hardening.
- Public API expands through `SafeFetchConfig`, `SafeFetchResult`, new result metadata dataclasses, new exception classes, and documented policy presets.
- CLI expands with new `SAFE_FETCH_*` environment variables.
- New or optional dependencies may be introduced for robust URL handling, Markdown AST processing, property-based tests, DNS testing, and optional rendered-text extraction.
- Tests expand substantially, including unit, integration, adversarial fixture, property-based, and CLI contract tests.
