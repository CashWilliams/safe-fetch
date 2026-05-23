# safe-fetch

Secure async web fetching for AI agents. Combines pre-request secret/PII scanning, SSRF blocking, and post-fetch prompt injection detection into a single `safe_fetch()` call.

## Quick Start

```python
from safe_fetch import safe_fetch, SafeFetchConfig, Policy

result = await safe_fetch("https://example.com/article")
print(result.content)          # clean markdown
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
| `STRICT` | Raise `SecretLeakError` / `PIILeakError` on any finding | Raise `InjectionDetectedError` on HIGH-confidence finding |
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
    llm_client: Any = None               # optional; must implement classify_injection(text) -> bool
    user_agent: str = "safe-fetch/1.0 (LLM-agent)"
    extra_headers: dict = field(default_factory=dict)
```

## Fetch Pipeline

Content is retrieved in this order, returning at the first success:

1. **Content negotiation** — `Accept: text/markdown` header; if server returns markdown/plain text, used directly (`extraction_method="content-negotiation"`)
2. **llms.txt** — checks `<scheme>://<host>/llms.txt`; if found, returns curated LLM content (`extraction_method="llms-txt"`)
3. **trafilatura** — extracts main content from HTML as markdown (`extraction_method="trafilatura"`)
4. **readability + markdownify** — fallback HTML extraction (`extraction_method="readability+markdownify"`)

## Exception Reference

All exceptions inherit from `SafeFetchError`.

| Exception | When raised |
|---|---|
| `InvalidSchemeError` | URL scheme is not `http` or `https` |
| `SSRFBlockedError` | URL resolves to a private/reserved IP (always raised) |
| `SecretLeakError` | Secret detected in URL query params or headers (`STRICT`) |
| `PIILeakError` | PII (email, phone, credit card, SSN) detected in URL or headers (`STRICT`) |
| `FetchTimeoutError` | Connect or read timeout (`.phase` = `"connect"` or `"read"`) |
| `ExtractionFailedError` | All extraction methods failed |
| `InjectionDetectedError` | HIGH-confidence injection pattern in response (`STRICT`) |

```python
from safe_fetch import SafeFetchError

try:
    result = await safe_fetch(url)
except SafeFetchError as e:
    print(f"safe-fetch error: {e}")
```

## Optional LLM Escalation

For borderline injection cases (MEDIUM heuristic confidence), provide an `llm_client` that implements `classify_injection(text: str) -> bool`. This is called at most once per fetch and only when structural heuristics score above threshold.

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
