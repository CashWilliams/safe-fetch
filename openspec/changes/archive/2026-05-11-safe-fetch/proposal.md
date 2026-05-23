## Why

AI agents that fetch web content are exposed to two critical risks: indirect prompt injection in responses (adversarial instructions embedded in fetched pages) and accidental sensitive data leakage in requests (secrets, tokens, or PII embedded in URLs or headers). No existing Python tool combines these protections with clean LLM-ready output.

## What Changes

- New Python package `safe-fetch` providing a single async function for agents to safely retrieve web content
- Pre-request scanner that detects and blocks secrets, tokens, and PII in URLs and headers before the request is sent
- Post-fetch scanner that detects and filters prompt injection patterns in response content
- Smart fetch pipeline that negotiates markdown content, discovers `/llms.txt`, and falls back through extraction strategies
- Response normalization that returns clean markdown regardless of source format

## Capabilities

### New Capabilities

- `request-guard`: Pre-request security scanning — detects secrets (API keys, tokens, passwords) and PII (emails, phone numbers, credit cards) in URLs, query parameters, and headers. Blocks or warns before the request is made.
- `response-guard`: Post-fetch injection defense — heuristic and regex-based detection of prompt injection patterns, invisible/zero-width characters, and instruction-like content in fetched responses. Returns sanitized content or raises on high-confidence attacks.
- `fetch-pipeline`: Smart fetch orchestration — tries `Accept: text/markdown` content negotiation first, checks for `/llms.txt` at the domain root, falls back to trafilatura extraction, then readability-lxml + markdownify, with optional Playwright for JS-heavy pages.
- `safe-fetch-api`: Public-facing API — a single `safe_fetch(url, ...)` async function that composes all layers, with configurable policy modes (strict / warn / permissive) for both request and response scanning.

### Modified Capabilities

## Impact

- New package with no existing code to modify
- Dependencies: `httpx`, `detect-secrets`, `trafilatura`, `readability-lxml`, `markdownify`, `llms-txt`, `ssrf-protect`
- Optional dependency: `playwright` (for JS rendering fallback)
- Python 3.11+ required
- No on-box ML models — all scanning is entropy-based, regex, and heuristic
