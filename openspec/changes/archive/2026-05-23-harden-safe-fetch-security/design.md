## Context

safe-fetch currently provides a single async Python API and CLI that perform request leak checks, SSRF checks, HTTP fetch, content extraction, response injection scanning, and nonce-backed content wrapping. Recent review work aligned the current specs with the implementation, added redirect-limit handling, and made active OpenSpec validation pass.

The project’s security boundary is broader than ordinary web fetching. Callers are expected to pass returned content into AI agents or RAG pipelines, where remote page content can influence privileged actions if it is not clearly treated as untrusted data. The design therefore needs to harden both network access and content handling while preserving a small public API.

Current constraints:
- Python 3.11+ package using `httpx`, `detect-secrets`, `trafilatura`, `readability-lxml`, and `markdownify`.
- CLI configuration is controlled through environment variables so agents cannot weaken policy per invocation.
- OpenSpec specs are the source of truth for behavior.
- Existing public names should remain compatible where possible; new behavior should default safer.

## Goals / Non-Goals

**Goals:**
- Make URL validation and connection behavior resistant to common SSRF parser bypasses and DNS rebinding.
- Ensure request leak scanning happens before network access and never stores raw secrets in findings or metadata.
- Add hard resource limits for response size, total fetch deadline, status codes, content types, and extraction concurrency.
- Produce safer Markdown by default for LLM use while preserving raw extracted content for callers that need it.
- Improve prompt-injection handling for Unicode-normalized matches, Markdown/HTML injection, hidden text, and classifier failures.
- Return provenance, integrity, and risk metadata that downstream agents can audit.
- Add policy presets and fail-closed controls suitable for stricter deployments.
- Build an adversarial test suite that captures known SSRF and prompt-injection failure modes.

**Non-Goals:**
- Proving fetched content is safe to obey as instructions.
- Providing a full browser isolation product.
- Building a general-purpose crawler.
- Supporting arbitrary authenticated websites or cookies.
- Guaranteeing perfect semantic prompt-injection detection.
- Replacing caller-side least privilege, source allowlisting, human approval, or tool sandboxing.

## Decisions

### 1. Add a Canonical URL Object

Create an internal `_url.py` module with a `CanonicalURL` dataclass and `canonicalize_url(raw_url, config)` function. All request scanning, SSRF checks, fetching, redirect validation, `.md` probe construction, boundary metadata, and provenance should use this object instead of repeatedly parsing raw strings.

The canonicalizer rejects:
- Missing host, invalid port, non-HTTP(S) scheme, fragments, URL userinfo, backslashes, control characters, and empty netloc.
- Hostnames whose NFKC or IDNA processing changes meaning in unsafe ways.
- Ambiguous IP literals or host encodings, including decimal/octal IPv4, IPv4-mapped IPv6, malformed IPv6 brackets, and local aliases.
- Plain HTTP when `allow_http=False`.

Rationale: Python’s URL parser is useful but intentionally not a security validator. A single canonicalization path avoids inconsistent parser decisions across guards and fetch code.

Alternatives considered:
- Keep ad hoc `urllib.parse` calls: rejected because validation behavior is scattered.
- Switch entirely to a third-party URL parser: possible, but still requires project-specific security rules.

### 2. Enforce Network Access at Connect Time

Add rebinding-safe resolution and connection behavior. The preferred implementation is a custom transport/resolver wrapper around `httpx` that validates every resolved A/AAAA address immediately before connect and pins the validated address for that connection. If that proves too invasive, use an audited dependency that provides equivalent `httpx` SSRF protection and wrap it behind an internal adapter.

Network validation should use an allow-global default: permit only globally routable addresses unless explicitly allowed. Host/CIDR allowlists and blocklists are evaluated before connection.

Rationale: resolving in `check_ssrf()` and later letting `httpx` resolve again creates a TOCTOU DNS rebinding gap.

Alternatives considered:
- Validate DNS once before `httpx`: rejected because it does not close the rebinding window.
- Disable DNS hostnames entirely: too restrictive for normal web fetching.

### 3. Split Security Policy into Focused Controls

Keep the existing `Policy` enum but add explicit config fields for boundary-specific behavior:
- `allow_http`
- `allowed_hosts`
- `allowed_host_suffixes`
- `blocked_hosts`
- `blocked_cidrs`
- `max_response_bytes`
- `total_timeout`
- `allowed_content_types`
- `http_status_policy`
- `redaction_mode`
- `safe_markdown`
- `classifier_timeout`
- `classifier_failure_policy`
- `max_redirects`
- `max_extraction_workers`

Provide classmethod presets on `SafeFetchConfig`, such as `agent_default()`, `strict_enterprise()`, and `permissive_research()`.

Rationale: a single `request_policy` cannot express network, leak, classifier, and content behaviors cleanly.

Alternatives considered:
- Add many new `Policy` enum values: rejected because it would overload one axis with unrelated controls.

### 4. Add Safe Markdown as the LLM-Ready Output

Introduce a safe Markdown transformation stage after extraction and response scanning. `raw_content` remains the extracted/scanned Markdown; `safe_content` is a neutralized Markdown representation; `content` wraps `safe_content` by default.

The transformer should neutralize:
- Markdown images and reference images.
- Raw HTML blocks, comments, script-like tags, and embedded SVG.
- Autolinks and suspicious external links according to configurable link policy.
- Markdown constructs that can trigger external fetches or hide prompt text.

Rationale: Markdown can perform exfiltration or instruction hiding through image URLs, raw HTML, and comments. Boundary tags alone do not neutralize those constructs.

Alternatives considered:
- Regex-only Markdown rewriting: acceptable for a first narrow pass but brittle; prefer an AST parser if dependency cost is reasonable.
- Remove all links: safer but too destructive for documentation use; make link policy configurable.

### 5. Redact Using Match Ranges, Not Just Raw Regexes

Response scanning should preserve normalized detection while redacting the original output reliably. For normalized matches where exact source offsets cannot be mapped safely, redact a conservative original snippet or whole prose segment depending on `redaction_mode`.

Rationale: currently a Unicode-obfuscated injection can be detected in the normalized scan copy but missed by redaction over original text.

Alternatives considered:
- Normalize returned content: rejected because the existing spec intentionally preserves user-visible characters except invisible-stripping.

### 6. Expand HTML Sanitization Before Extraction

Enhance `sanitize_html()` to remove broader hidden-content vectors:
- `<style>` rules that hide matching classes/IDs.
- `aria-hidden`, `inert`, `input type=hidden`, SVG `<desc>`, SVG `<title>`, and `<foreignObject>`.
- `width:0`, `height:0`, `clip`, `clip-path`, transparent color, offscreen `right`/`bottom`, `transform`, and extreme z-index/positioning cases.

Add optional rendered visible-text extraction through a Playwright extra. This mode should compare rendered visible text against parser-extracted text and record hidden-content deltas.

Rationale: prompt injection frequently hides content from humans while leaving it visible to parsers.

Alternatives considered:
- Always use Playwright: rejected due to dependency weight and latency.

### 7. Add Provenance and Risk Metadata

Add structured dataclasses for:
- `FetchMetadata`: final URL, redacted source URL, source host, content type, content length, ETag, Last-Modified, redirect chain, fetched_at, elapsed_ms.
- `ContentIntegrity`: hashes for raw and safe content.
- `SafetyEvent`: sanitizer removals, redactions, blocked Markdown elements, classifier outcomes, policy decisions.
- `RiskAssessment`: score, level, reasons.

`SafeFetchResult` should expose these while keeping existing fields.

Rationale: downstream agents need enough metadata to decide whether to trust, cite, cache, or reject content.

Alternatives considered:
- Put all metadata in an untyped dict: rejected because typed metadata is easier to test and document.

### 8. Fail Closed for High-Risk Presets

Default agent behavior should remain ergonomic, but strict presets should block on ambiguous states:
- DNS validation failure.
- Classifier failure when classifier is configured.
- Sanitizer/parser errors.
- Unsupported content type.
- Oversized response.
- Unknown status behavior.

Rationale: enterprise and high-risk agent workflows should prefer missing data over unsafe data.

Alternatives considered:
- Always fail closed: safer but likely too disruptive for ordinary content fetching.

### 9. Treat Testing as a First-Class Capability

Add `tests/security/` with fixture corpora and property-based tests. Tests should cover parser bypasses, DNS rebinding, redirect validation, max-size streaming, status/content-type policy, hidden HTML/CSS payloads, Unicode prompt injection, Markdown exfiltration, and CLI/env coverage.

CI should run with warnings as errors and include lint/type/security audit tasks where available.

Rationale: this project’s correctness depends on adversarial edge cases, not only happy-path behavior.

Alternatives considered:
- Only add targeted unit tests: rejected because parser/network security requires broad corpus and fuzz coverage.

## Risks / Trade-offs

- DNS rebinding-safe transport may be complex → Start with a narrow adapter and tests; evaluate existing audited libraries before writing low-level socket code.
- Strict URL rules may reject some valid but unusual URLs → Prefer explicit config escape hatches over weakening defaults.
- Safe Markdown transformation may alter useful documentation → Preserve `raw_content`, record `SafetyEvent`s, and make link policy configurable.
- Playwright visible-text mode adds latency and installation size → Keep it optional behind an extra and config flag.
- Risk scoring can imply false precision → Return reasoned categorical levels and document that the score is advisory.
- New config fields increase API surface → Group fields carefully, provide presets, and maintain backwards-compatible defaults where possible.
- Comprehensive tests may slow CI → Separate fast unit corpus from slower browser/property suites, but run security-critical tests in default CI.

## Migration Plan

1. Add new dataclasses, exceptions, config fields, and internal modules without changing default import names.
2. Implement canonical URL validation and update request guard, fetch pipeline, redirects, and `.md` probe to use it.
3. Add rebinding-safe transport or dependency-backed adapter and wire it into fetch.
4. Add fetch limits and status/content-type policy.
5. Add safe Markdown transformation and provenance/risk metadata.
6. Expand response and HTML sanitization.
7. Add CLI env vars and README/security documentation.
8. Add adversarial tests and run the existing suite after each phase.
9. Preserve old fields in `SafeFetchResult`; introduce new fields with defaults to minimize caller breakage.

Rollback strategy: because this expands behavior behind typed config defaults, rollback can disable new safe Markdown and strict resource controls through config while retaining security bug fixes. For breaking defaults such as HTTPS-only, document migration and provide an explicit opt-in compatibility preset if needed.

## Open Questions

- Which URL parser or IDNA handling dependency, if any, should be adopted instead of standard library primitives?
- Should `allow_http` default to `False` immediately, or should this be introduced through `strict_enterprise()` first?
- Should `content` wrap `safe_content` by default in all modes, or should a compatibility setting keep wrapping `raw_content`?
- What exact scoring weights should be used for `RiskAssessment`?
- Should browser-rendered visible-text extraction be part of this change’s implementation or specified as optional follow-up work?
