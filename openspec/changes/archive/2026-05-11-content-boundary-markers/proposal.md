## Why

When safe-fetch returns web content to an LLM, the model has no way to distinguish where the trusted system context ends and untrusted external content begins — making it vulnerable to prompt injection via crafted web pages. Adding per-fetch content boundary markers with a cryptographically unpredictable nonce gives the LLM (and the operator's system prompt) a verifiable signal that what follows is untrusted external data.

## What Changes

- `SafeFetchResult` gains a `content_marker` field: the random nonce generated for this fetch
- `safe_fetch()` wraps `content` in XML-style boundary tags on every successful fetch, embedding the nonce, source URL, and fetch timestamp in the opening tag and the nonce alone in the closing tag
- Raw `content` (unwrapped) remains accessible as `result.raw_content`; `result.content` now contains the wrapped form
- The CLI default output prints the wrapped content; `--json` includes both `content` (wrapped), `raw_content`, and `content_marker`
- No new dependencies — `secrets` and `datetime` are stdlib

## Capabilities

### New Capabilities
- `content-boundary-markers`: Per-fetch nonce generation, XML-style wrapping of fetched content with `untrusted="true"`, `source`, `fetched_at`, and matching `marker` attributes on both open and close tags

### Modified Capabilities
- `safe-fetch-api`: `SafeFetchResult` gains `content_marker` (str) and `raw_content` (str) fields; `content` field now contains wrapped output
- `cli`: Default stdout output changes from raw markdown to wrapped content; `--json` output adds `raw_content` and `content_marker` fields

## Impact

- `safe_fetch/_types.py`: `SafeFetchResult` gets two new fields
- `safe_fetch/__init__.py`: wrapping step added after response guard
- `safe_fetch/_cli.py`: no logic changes needed — wrapping is done in the library layer
- Tests: existing tests that assert on `result.content` need updating; new tests for marker format and nonce uniqueness
