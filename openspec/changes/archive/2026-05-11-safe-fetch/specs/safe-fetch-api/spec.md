## ADDED Requirements

### Requirement: Single async entry point
The package SHALL expose a single public async function `safe_fetch(url, ...)` that composes request guard, fetch pipeline, and response guard in order. Callers SHALL NOT need to import or instantiate internal modules.

#### Scenario: Basic usage returns clean markdown
- **WHEN** `result = await safe_fetch("https://example.com/article")` is called
- **THEN** `result.content` is a markdown string, `result.url` is the final URL after redirects, and `result.extraction_method` indicates how the content was obtained

#### Scenario: Import surface is minimal
- **WHEN** a caller does `from safe_fetch import safe_fetch, SafeFetchConfig`
- **THEN** these are the only two names needed for all standard usage

### Requirement: SafeFetchConfig dataclass
The package SHALL provide a `SafeFetchConfig` dataclass with fields:
- `request_policy: Policy = Policy.STRICT` — governs pre-request scanning behavior
- `response_policy: Policy = Policy.WARN` — governs post-fetch scanning behavior
- `connect_timeout: float = 10.0` — seconds
- `read_timeout: float = 30.0` — seconds
- `llm_client: Any = None` — optional client for LLM escalation; must implement `classify_injection(text: str) -> bool`
- `user_agent: str = "safe-fetch/1.0 (LLM-agent)"` — sent with every request
- `extra_headers: dict = field(default_factory=dict)` — additional headers (scanned by request guard)

#### Scenario: Default config is safe out of the box
- **WHEN** `safe_fetch(url)` is called with no config argument
- **THEN** `SafeFetchConfig()` defaults are used: STRICT request policy, WARN response policy, no LLM escalation

#### Scenario: Custom config is passed through all layers
- **WHEN** `safe_fetch(url, config=SafeFetchConfig(response_policy=Policy.STRICT))` is called
- **THEN** the response guard uses STRICT policy, raising on any finding

### Requirement: SafeFetchResult dataclass
The `safe_fetch` function SHALL return a `SafeFetchResult` dataclass with fields:
- `content: str` — clean markdown content
- `url: str` — final URL after redirects
- `status_code: int` — HTTP status of the final response
- `extraction_method: str` — one of: `"content-negotiation"`, `"llms-txt"`, `"trafilatura"`, `"readability+markdownify"`
- `request_findings: list[RequestFinding]` — secret/PII findings from pre-request scan (empty if none)
- `response_findings: list[InjectionFinding]` — injection findings from response scan (empty if none)

#### Scenario: Result is fully populated on success
- **WHEN** `safe_fetch` completes successfully
- **THEN** all fields of `SafeFetchResult` are populated; `request_findings` and `response_findings` are empty lists if no issues were found

### Requirement: Policy enum
The package SHALL expose a `Policy` enum with values `STRICT`, `WARN`, and `PERMISSIVE`. `STRICT` raises on any finding. `WARN` logs and continues (content may be redacted). `PERMISSIVE` passes through with findings recorded. SSRF blocking is not subject to policy — it always enforces.

#### Scenario: Policy.STRICT raises on request finding
- **WHEN** a secret is found in the URL under `Policy.STRICT`
- **THEN** `SecretLeakError` (subclass of `SafeFetchError`) is raised

#### Scenario: Policy.PERMISSIVE records but does not block
- **WHEN** `response_policy=Policy.PERMISSIVE` and injection patterns are found
- **THEN** findings are recorded in `result.response_findings` but content is returned unmodified

### Requirement: Exception hierarchy
The package SHALL define a clear exception hierarchy rooted at `SafeFetchError`:
- `SafeFetchError` (base)
  - `SecretLeakError` — secret detected in request
  - `PIILeakError` — PII detected in request
  - `SSRFBlockedError` — SSRF / private IP blocked (always raised regardless of policy)
  - `InvalidSchemeError` — disallowed URL scheme
  - `InjectionDetectedError` — injection detected in response under STRICT policy
  - `ExtractionFailedError` — all extraction methods failed
  - `FetchTimeoutError` — connect or read timeout

#### Scenario: All errors are catchable as SafeFetchError
- **WHEN** any error condition occurs
- **THEN** `except SafeFetchError` catches it, allowing callers to handle all safe-fetch errors uniformly

#### Scenario: SSRFBlockedError cannot be suppressed by policy
- **WHEN** `request_policy=Policy.PERMISSIVE` and the URL resolves to a private IP
- **THEN** `SSRFBlockedError` is still raised — it is not subject to policy
