## Purpose
Define the public Python API, configuration, result shape, policies, and exception hierarchy for safe-fetch.
## Requirements
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
- `request_policy: Policy = Policy.STRICT` — governs pre-request leak scanning behavior
- `response_policy: Policy = Policy.WARN` — governs post-fetch scanning behavior
- `connect_timeout: float = 10.0` — seconds
- `read_timeout: float = 30.0` — seconds
- `total_timeout: float | None = 60.0` — full-operation wall-clock timeout in seconds
- `max_response_bytes: int = 10_000_000` — maximum streamed response body size
- `max_redirects: int = 5` — maximum redirect hops
- `max_extraction_workers: int = 4` — maximum concurrent blocking extraction workers
- `llm_client: Any = None` — optional client for LLM escalation; must implement sync or async `classify_injection(text: str) -> bool`
- `classifier_timeout: float = 5.0` — maximum seconds for classifier escalation
- `classifier_failure_policy: Policy = Policy.WARN` — governs classifier failure behavior
- `user_agent: str = "safe-fetch/1.0 (LLM-agent)"` — sent with every request
- `extra_headers: dict = field(default_factory=dict)` — additional headers scanned by request guard
- `allow_http: bool = True` — whether plain HTTP URLs are allowed
- `allowed_hosts: set[str] = field(default_factory=set)` — exact host allowlist; empty means no exact allowlist
- `allowed_host_suffixes: set[str] = field(default_factory=set)` — suffix allowlist; empty means no suffix allowlist
- `blocked_hosts: set[str] = field(default_factory=set)` — exact hosts to deny
- `blocked_cidrs: set[str] = field(default_factory=set)` — CIDR ranges to deny
- `allowed_cidrs: set[str] = field(default_factory=set)` — CIDR ranges explicitly allowed
- `allowed_content_types: set[str] = field(default_factory=lambda: {"text/html", "text/plain", "text/markdown", "application/xhtml+xml"})`
- `http_status_policy: str = "2xx"` — default success status policy
- `redaction_mode: str = "snippet"` — one of `"none"`, `"pattern"`, `"snippet"`, `"segment"`, `"document"`
- `safe_markdown: bool = True` — whether wrapped `content` uses safe Markdown
- `rendered_text_mode: bool = False` — whether optional browser-rendered visible-text extraction is enabled

The package SHALL provide preset constructors `SafeFetchConfig.agent_default()`, `SafeFetchConfig.strict_enterprise()`, and `SafeFetchConfig.permissive_research()`.

#### Scenario: Default config is safe out of the box
- **WHEN** `safe_fetch(url)` is called with no config argument
- **THEN** `SafeFetchConfig.agent_default()` compatible defaults are used with strict request leak policy, warn response policy, response limits, safe Markdown enabled, and no LLM escalation

#### Scenario: Strict preset fails closed
- **WHEN** `SafeFetchConfig.strict_enterprise()` is used
- **THEN** HTTP, unknown hosts outside allow policy, unsupported content types, classifier failures, and ambiguous safety states are blocked according to strict configuration

#### Scenario: Custom config is passed through all layers
- **WHEN** `safe_fetch(url, config=SafeFetchConfig(response_policy=Policy.STRICT, max_response_bytes=1024))` is called
- **THEN** the response guard uses STRICT policy and the fetch pipeline enforces the byte limit

### Requirement: SafeFetchResult dataclass
The `safe_fetch` function SHALL return a `SafeFetchResult` dataclass with fields:
- `content: str` — fetched content wrapped in `<web_content>` boundary tags using safe Markdown by default
- `raw_content: str` — clean extracted Markdown content before safe Markdown transformation and without boundary tags
- `safe_content: str` — transformed safe Markdown content without boundary tags
- `content_marker: str` — the 32-character hex nonce embedded in both boundary tags
- `url: str` — final URL after redirects
- `status_code: int` — HTTP status of the final response
- `extraction_method: str` — one of: `"content-negotiation"`, `"md-probe"`, `"trafilatura"`, `"readability+markdownify"`
- `request_findings: list[RequestFinding]` — secret/PII findings from pre-request scan (empty if none)
- `response_findings: list[InjectionFinding]` — injection findings from response scan (empty if none)
- `metadata: FetchMetadata` — provenance and fetch metadata
- `integrity: ContentIntegrity` — content hashes
- `safety_events: list[SafetyEvent]` — sanitizer, redaction, and policy events
- `risk: RiskAssessment` — aggregate risk score, level, and reasons

#### Scenario: Result is fully populated on success
- **WHEN** `safe_fetch` completes successfully
- **THEN** all fields of `SafeFetchResult` are populated; `content` is wrapped, `raw_content` and `safe_content` are plain Markdown strings, `content_marker` is a 32-char hex nonce, findings are empty lists if no issues were found, and metadata/integrity/risk fields are present

#### Scenario: content field contains boundary tags
- **WHEN** `safe_fetch` completes successfully
- **THEN** `result.content` starts with `<web_content untrusted="true"` and ends with `</web_content marker="...">`

#### Scenario: raw and safe content are distinct when transformation occurs
- **WHEN** safe Markdown transformation neutralizes content
- **THEN** `result.raw_content` preserves the pre-transform Markdown and `result.safe_content` contains the transformed Markdown

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
  - `InvalidURLError` — malformed, ambiguous, or unsafe URL
  - `HostPolicyError` — host or CIDR policy rejected a target
  - `InjectionDetectedError` — injection detected in response under STRICT policy
  - `ExtractionFailedError` — all extraction methods failed
  - `FetchTimeoutError` — connect, read, or total timeout
  - `RedirectLimitError` — HTTP redirect limit exceeded
  - `ResponseTooLargeError` — response body exceeded configured byte limit
  - `UnsupportedContentTypeError` — response content type is not allowed
  - `HTTPStatusError` — HTTP status policy rejected the response
  - `ClassifierError` — classifier escalation failed under fail-closed policy

#### Scenario: All errors are catchable as SafeFetchError
- **WHEN** any error condition occurs
- **THEN** `except SafeFetchError` catches it, allowing callers to handle all safe-fetch errors uniformly

#### Scenario: SSRFBlockedError cannot be suppressed by policy
- **WHEN** `request_policy=Policy.PERMISSIVE` and the URL resolves to a private IP
- **THEN** `SSRFBlockedError` is still raised because it is not subject to leak policy

