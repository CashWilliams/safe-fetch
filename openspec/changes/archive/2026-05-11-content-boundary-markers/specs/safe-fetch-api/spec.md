## MODIFIED Requirements

### Requirement: SafeFetchResult dataclass
The `safe_fetch` function SHALL return a `SafeFetchResult` dataclass with fields:
- `content: str` — fetched content wrapped in `<web_content>` boundary tags (LLM-ready form)
- `raw_content: str` — clean markdown content without boundary tags (processing-ready form)
- `content_marker: str` — the 32-character hex nonce embedded in both boundary tags
- `url: str` — final URL after redirects
- `status_code: int` — HTTP status of the final response
- `extraction_method: str` — one of: `"content-negotiation"`, `"llms-txt"`, `"trafilatura"`, `"readability+markdownify"`
- `request_findings: list[RequestFinding]` — secret/PII findings from pre-request scan (empty if none)
- `response_findings: list[InjectionFinding]` — injection findings from response scan (empty if none)

#### Scenario: Result is fully populated on success
- **WHEN** `safe_fetch` completes successfully
- **THEN** all fields of `SafeFetchResult` are populated; `content` is wrapped, `raw_content` is plain markdown, `content_marker` is a 32-char hex nonce; `request_findings` and `response_findings` are empty lists if no issues were found

#### Scenario: content field contains boundary tags
- **WHEN** `safe_fetch` completes successfully
- **THEN** `result.content` starts with `<web_content untrusted="true"` and ends with `</web_content marker="...">` 

#### Scenario: raw_content matches pre-wrap markdown
- **WHEN** `safe_fetch` completes successfully
- **THEN** `result.raw_content` is the plain markdown string as returned by the extraction + response guard pipeline, without any wrapping
