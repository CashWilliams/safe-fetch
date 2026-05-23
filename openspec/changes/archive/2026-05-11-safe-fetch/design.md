## Context

AI agents making web requests face two distinct attack surfaces: outbound (leaking secrets in URLs/headers) and inbound (receiving adversarial content that hijacks agent behavior). No existing Python library addresses both. The tool must be lightweight — no on-box ML models — and integrate cleanly as a single async function that agents can use as a drop-in replacement for `httpx.get`.

## Goals / Non-Goals

**Goals:**
- Single async `safe_fetch(url)` entry point usable by any Python AI agent
- Pre-request scanning for secrets and PII with configurable block/warn policy
- Post-fetch heuristic injection detection with configurable reject/sanitize/warn policy
- Clean markdown output via content negotiation → llms.txt → trafilatura → fallback chain
- Zero on-box ML; all detection is entropy-based, regex, or structural heuristics
- Optional escalation to an LLM API call for ambiguous injection cases

**Non-Goals:**
- JavaScript rendering (Playwright) is optional and not in the default install
- Not a general HTTP client — only GET is supported in v1
- Not a content crawler or spider
- No authentication / cookie handling in v1
- Not responsible for agent-level trust decisions — it surfaces risk, policy is caller's

## Decisions

### 1. Pre-request scanning: detect-secrets + regex PII, not Presidio

**Decision**: Use `detect-secrets` for secret/token detection and hand-rolled regex for PII. Drop Presidio.

**Rationale**: Presidio's default NER recognizers load spaCy models at import time — violates the no-ML-on-box constraint. `detect-secrets` is pure entropy + regex (25+ detectors: AWS keys, GitHub tokens, high-entropy strings, etc.) and operates on plain strings. PII in URLs is structurally constrained (emails, phone numbers, credit cards) and well-covered by regex without NER.

**Alternatives considered**: Presidio pattern-only mode (no NER) is possible but adds a heavy dependency for coverage equivalent to ~50 lines of regex.

### 2. Post-fetch injection: heuristic + regex layers, optional LLM escalation

**Decision**: Layer 1 = invisible/zero-width character stripping (always on). Layer 2 = regex patterns for known injection phrases. Layer 3 = structural heuristics (instruction density, role-play framing, system prompt patterns). Optional Layer 4 = single LLM API call for ambiguous content when caller provides a client.

**Rationale**: llm-guard's `PromptInjection` scanner runs DeBERTa locally — ruled out. Pure regex catches known attacks (ignore previous instructions, disregard, system:, [INST], etc.) and is fast. Structural heuristics catch novel patterns: high ratio of imperative sentences, presence of `<system>` / `<|im_start|>` tokens, instruction-like markdown headers in unexpected context. The LLM escalation path is opt-in and only fires when heuristics produce a borderline score, keeping cost minimal.

**Alternatives considered**: Calling an LLM on every fetch is too expensive and adds latency. Regex-only misses creative injections. The layered approach gives defense-in-depth without ML cost.

### 3. Fetch pipeline: negotiate → llms.txt → trafilatura → fallback

**Decision**: Always try `Accept: text/markdown` first. On HTML response, check `/{domain}/llms.txt` for LLM-curated content. Fall back to trafilatura (best general extractor), then readability-lxml + markdownify.

**Rationale**: Content negotiation is free — if the server supports it (Cloudflare, Vercel, some docs sites) you get clean markdown with zero processing. llms.txt gives site-curated context when available. trafilatura outperforms readability on general web content and natively outputs markdown. The fallback chain is ordered by quality, not speed.

**Alternatives considered**: Firecrawl self-hosted covers the extraction layer well but adds Docker infrastructure. Jina `r.jina.ai` prefix is not self-hostable. Both are external services.

### 4. Package structure: four modules, one public function

**Decision**: Internal modules `_request_guard`, `_response_guard`, `_fetch_pipeline`, `_extractor`. Public API is `safe_fetch()` in `__init__.py` plus a `SafeFetchConfig` dataclass.

**Rationale**: Keeps the surface area minimal. Each layer is independently testable. Config is a single object passed through rather than global state, making the tool safe for concurrent async use.

### 5. Policy modes: strict / warn / permissive

**Decision**: Both request and response guards accept a `Policy` enum: `STRICT` (raise on any finding), `WARN` (log and continue), `PERMISSIVE` (pass through, metrics only).

**Rationale**: Agents in production may need to fetch known-clean internal URLs that trip heuristics. Callers need an escape hatch without forking the library. `WARN` is the default for response guard; `STRICT` is the default for request guard since leaking secrets outbound is unambiguously bad.

## Risks / Trade-offs

- **False positives on injection detection** → Heuristics tuned conservatively; `WARN` default gives callers visibility without breaking flows. Threshold config exposed.
- **False negatives on novel injection** → Regex/heuristic layers are not exhaustive. The optional LLM escalation call is the mitigation for high-risk contexts.
- **trafilatura extraction quality varies** → Fallback chain covers most cases; caller receives a `extraction_method` field in result so they can inspect which strategy was used.
- **detect-secrets entropy threshold** → High-entropy strings produce false positives on things like base64 image data in URLs. Scope scanning to query params and header values only (not full URL path) to reduce noise.
- **llms.txt not widely adopted** → Discovery is a best-effort check with a short timeout; failure is silent and falls through to normal extraction.
- **DNS rebinding / SSRF** → `ssrf-protect` handles private IP blocking; atomic DNS resolution (resolve once, connect to that IP, no re-resolve) requires care with httpx transport layer.

## Resolved Decisions

- **GET only in v1** — POST is out of scope; request body scanning deferred. Design request guard as body-aware internally so POST can be added without rework.
- **Timeouts: 10s connect, 30s read** — conservative defaults suitable for internet-facing agent use.
- **LLM escalation uses a custom 1-method protocol** — `classify_injection(text: str) -> bool`. Callers wrap their SDK of choice; no coupling to OpenAI or any specific client shape.
- **Injection findings are structured metadata on result always** — `response_findings` populated on every call; exceptions raised on `STRICT`, redaction + log on `WARN`, pass-through on `PERMISSIVE`.
