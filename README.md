# safe-fetch

Secure async web fetching for AI agents. Combines pre-request secret/PII scanning, SSRF blocking, and post-fetch prompt injection detection into a single `safe_fetch()` call.

## Quick Start

```python
from safe_fetch import safe_fetch, SafeFetchConfig, Policy

result = await safe_fetch("https://example.com/article")
print(result.content)          # wrapped, LLM-ready markdown
print(result.raw_content)      # unwrapped markdown
print(result.safe_content)     # unwrapped safe markdown
print(result.metadata.final_url)
print(result.risk.level)
print(result.extraction_method)  # how it was obtained
print(result.response_findings)  # injection findings (empty if clean)
```

```python
# Custom policy
config = SafeFetchConfig(
    request_policy=Policy.STRICT,   # raise on secrets/PII in URL/headers
    response_policy=Policy.WARN,    # log + redact injections, don't raise
)
result = await safe_fetch("https://example.com/docs", config=config)
```

## Policy Modes

Both `request_policy` and `response_policy` accept a `Policy` enum value.

| Policy | Request behavior | Response behavior |
|---|---|---|
| `STRICT` | Raise `SecretLeakError` / `PIILeakError` on any finding | Raise `InjectionDetectedError` on any finding |
| `WARN` | Log finding, record in `request_findings`, continue | Log finding, redact matched content, record in `response_findings` |
| `PERMISSIVE` | Record in `request_findings`, continue | Record in `response_findings`, return content unmodified |

> **Note:** SSRF blocking is **always enforced** regardless of `request_policy`. `SSRFBlockedError` is never suppressed.

**Defaults:** `request_policy=STRICT`, `response_policy=WARN`

## SafeFetchConfig

```python
@dataclass
class SafeFetchConfig:
    request_policy: Policy = Policy.STRICT
    response_policy: Policy = Policy.WARN
    connect_timeout: float = 10.0        # seconds
    read_timeout: float = 30.0           # seconds
    total_timeout: float | None = 60.0
    max_response_bytes: int = 10_000_000
    max_redirects: int = 5
    allow_http: bool = True
    allowed_hosts: set[str] = field(default_factory=set)
    blocked_cidrs: set[str] = field(default_factory=set)
    allowed_content_types: set[str] = field(default_factory=lambda: {
        "text/html", "text/plain", "text/markdown", "application/xhtml+xml"
    })
    safe_markdown: bool = True
    llm_client: Any = None               # optional; must implement classify_injection(text) -> bool
    classifier_timeout: float = 5.0
    classifier_failure_policy: Policy = Policy.WARN
    user_agent: str = "safe-fetch/1.0 (LLM-agent)"
    extra_headers: dict = field(default_factory=dict)
```

Preset constructors are available:

```python
SafeFetchConfig.agent_default()
SafeFetchConfig.strict_enterprise()
SafeFetchConfig.permissive_research()
```

## Fetch Pipeline

Content is retrieved in this order, returning at the first success:

1. **Content negotiation** — `Accept: text/markdown` header; if server returns markdown/plain text, used directly (`extraction_method="content-negotiation"`)
2. **.md probe** — for HTML responses, probes the same path with `.md` appended while extraction runs (`extraction_method="md-probe"`)
3. **trafilatura** — extracts main content from HTML as markdown (`extraction_method="trafilatura"`)
4. **readability + markdownify** — fallback HTML extraction (`extraction_method="readability+markdownify"`)

The pipeline canonicalizes every caller URL, redirect target, and `.md` probe before network access. By default it blocks non-global destination addresses, local hostnames, ambiguous IP encodings, URL credentials, fragments, malformed ports, unsupported content types, non-2xx statuses, oversized responses, and redirect chains beyond `max_redirects`.

## Safe Markdown and Metadata

`result.raw_content` preserves extracted Markdown after response scanning. `result.safe_content` neutralizes Markdown images, reference images, raw HTML, comments, SVG/script/template/noscript blocks, autolinks, and active links while preserving visible text. `result.content` wraps `safe_content` in `<web_content>` boundary tags with a redacted source URL and timestamp.

`result.metadata`, `result.integrity`, `result.safety_events`, and `result.risk` provide provenance, SHA-256 content hashes, sanitizer/neutralization/classifier events, and an advisory risk score with reasons. The risk score is not a trust guarantee; treat fetched content as untrusted data and keep tools, credentials, and approvals least-privileged.

## CLI Environment Controls

The CLI is configured only through `SAFE_FETCH_*` environment variables, including policy, timeout, response size, redirect, host/CIDR, content-type, status, redaction, safe Markdown, and classifier controls:

```bash
SAFE_FETCH_MAX_RESPONSE_BYTES=1048576 \
SAFE_FETCH_ALLOWED_HOST_SUFFIXES=.example.com \
SAFE_FETCH_SAFE_MARKDOWN=true \
safe-fetch --json https://docs.example.com/page
```

Run `safe-fetch --help` for the full environment variable and exit code table.

## Exception Reference

All exceptions inherit from `SafeFetchError`.

| Exception | When raised |
|---|---|
| `InvalidSchemeError` | URL scheme is not `http` or `https` |
| `InvalidURLError` | URL is malformed, ambiguous, or unsafe |
| `HostPolicyError` | Host or CIDR policy rejected the target |
| `SSRFBlockedError` | URL resolves to a private/reserved IP (always raised) |
| `SecretLeakError` | Secret detected in URL query params or headers (`STRICT`) |
| `PIILeakError` | PII (email, phone, credit card, SSN) detected in URL or headers (`STRICT`) |
| `FetchTimeoutError` | Connect, read, or total timeout |
| `RedirectLimitError` | Too many HTTP redirects |
| `ResponseTooLargeError` | Response exceeded `max_response_bytes` |
| `UnsupportedContentTypeError` | Content type is not allowlisted |
| `HTTPStatusError` | Status policy rejected the response |
| `ClassifierError` | Classifier escalation failed under strict policy |
| `ExtractionFailedError` | All extraction methods failed |
| `InjectionDetectedError` | Injection finding in response (`STRICT`) |

## Threat Model and Residual Risk

safe-fetch is designed for untrusted web retrieval in agent and RAG workflows. It reduces SSRF, request secret leakage, hidden-content injection, Markdown exfiltration, and prompt-injection risks, but it does not prove remote content is safe to obey. Downstream systems should still separate instructions from retrieved data, restrict tool permissions, avoid passing secrets into retrieval URLs, prefer source allowlists, and require human approval for sensitive actions.

```python
from safe_fetch import SafeFetchError

try:
    result = await safe_fetch(url)
except SafeFetchError as e:
    print(f"safe-fetch error: {e}")
```

## Optional LLM Escalation

For borderline injection cases (MEDIUM heuristic confidence), provide an `llm_client` that implements `classify_injection(text: str) -> bool` or an async equivalent. This is called at most once per fetch and only under `STRICT` or `WARN` when structural heuristics score above threshold.

```python
class MyLLMClient:
    async def classify_injection(self, text: str) -> bool:
        # Call your LLM API here
        ...

config = SafeFetchConfig(llm_client=MyLLMClient())
result = await safe_fetch(url, config=config)
```

## Installation

```bash
uv add safe-fetch
# With optional Playwright support for JS-heavy pages:
uv add "safe-fetch[playwright]"
```
