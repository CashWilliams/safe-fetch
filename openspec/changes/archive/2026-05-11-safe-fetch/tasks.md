## 1. Project Setup

- [x] 1.1 Create package structure: `safe_fetch/` with `__init__.py`, `_request_guard.py`, `_response_guard.py`, `_fetch_pipeline.py`, `_extractor.py`, `_types.py`, `_exceptions.py`
- [x] 1.2 Add `pyproject.toml` with dependencies: `httpx`, `detect-secrets`, `trafilatura`, `readability-lxml`, `markdownify`, `llms-txt`, `ssrf-protect`; optional extra `[playwright]`
- [x] 1.3 Define `Policy` enum and full exception hierarchy in `_exceptions.py`
- [x] 1.4 Define `SafeFetchConfig`, `SafeFetchResult`, `RequestFinding`, `InjectionFinding` dataclasses in `_types.py`

## 2. Request Guard

- [x] 2.1 Implement URL scheme validation (allow only `http`/`https`, raise `InvalidSchemeError` on others)
- [x] 2.2 Implement SSRF/private IP blocking using `ssrf-protect`; add atomic DNS resolution check (resolve → validate → connect to resolved IP)
- [x] 2.3 Implement secret scanning of URL query parameters using `detect-secrets` string-scanning API
- [x] 2.4 Implement PII regex recognizers: email, phone (E.164 + common formats), credit card (Luhn validation), SSN
- [x] 2.5 Implement header scanning (apply secret + PII detectors to header values)
- [x] 2.6 Wire policy modes: `STRICT` raises, `WARN` logs + records finding, `PERMISSIVE` records only; SSRF always raises regardless of policy
- [x] 2.7 Write unit tests for all request guard scenarios in spec

## 3. Fetch Pipeline

- [x] 3.1 Implement base `httpx.AsyncClient` fetch with `Accept: text/markdown, ...` header, configurable timeouts, and 5-hop redirect limit
- [x] 3.2 Implement redirect re-validation: each redirect target passes through request guard before following
- [x] 3.3 Implement content-type check: if response is `text/markdown` or `text/plain`, return body directly with `extraction_method="content-negotiation"`
- [x] 3.4 Implement llms.txt discovery: attempt `GET <scheme>://<host>/llms.txt` with 3s timeout; on HTTP 200 parse with `llms-txt` library and return curated content
- [x] 3.5 Implement timeout handling: map httpx timeout exceptions to `FetchTimeoutError` with `phase` field
- [x] 3.6 Write unit tests for pipeline scenarios (mock httpx responses)

## 4. Content Extractor

- [x] 4.1 Implement primary extraction: `trafilatura.extract(html, output_format="markdown")`; return with `extraction_method="trafilatura"` on success
- [x] 4.2 Implement fallback extraction: `readability-lxml` → `markdownify` on trafilatura `None` return; set `extraction_method="readability+markdownify"`
- [x] 4.3 Raise `ExtractionFailedError` when both extractors fail
- [x] 4.4 Write unit tests for extractor cascade with known HTML fixtures

## 5. Response Guard

- [x] 5.1 Implement invisible/zero-width character stripper (U+200B, U+200C, U+200D, U+2060, U+00AD, etc.); always applied regardless of policy
- [x] 5.2 Build injection pattern library: instruction override phrases, role-play hijacking, system prompt markers, exfiltration phrases
- [x] 5.3 Implement regex pattern matching against pattern library; classify findings as `HIGH` confidence
- [x] 5.4 Implement structural heuristic scorer: imperative sentence ratio, instruction-density, turn-delimiter presence; classify findings as `MEDIUM` confidence
- [x] 5.5 Wire policy modes: `STRICT` raises `InjectionDetectedError`, `WARN` redacts matched snippets and logs, `PERMISSIVE` records findings only
- [x] 5.6 Implement optional LLM escalation: when `llm_client` provided and finding is `MEDIUM`, call `llm_client.classify_injection(text)` and upgrade to `HIGH` if adversarial
- [x] 5.7 Write unit tests for all response guard scenarios including false-positive cases (recipe, tutorial content)

## 6. Public API

- [x] 6.1 Implement `safe_fetch(url, config=None)` in `__init__.py`: compose request guard → fetch pipeline → response guard in order
- [x] 6.2 Ensure `SafeFetchResult` is fully populated on every successful return path
- [x] 6.3 Write integration tests: full `safe_fetch()` call against mocked HTTP server covering each extraction method and each error path
- [x] 6.4 Write `README.md` with quick-start example, policy mode table, and exception reference
