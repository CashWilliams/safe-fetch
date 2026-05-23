## ADDED Requirements

### Requirement: Per-fetch nonce generation
`safe_fetch()` SHALL generate a cryptographically random nonce for every successful fetch using `secrets.token_hex(16)` (128 bits of entropy, 32 hex characters). The nonce SHALL be unique per fetch invocation and SHALL NOT be reused across calls.

#### Scenario: Nonce is unique per fetch
- **WHEN** `safe_fetch()` is called twice with the same URL
- **THEN** each `SafeFetchResult.content_marker` is a different 32-character hex string

#### Scenario: Nonce format is valid hex
- **WHEN** `safe_fetch()` succeeds
- **THEN** `result.content_marker` matches `^[0-9a-f]{32}$`

### Requirement: Content boundary wrapping
`safe_fetch()` SHALL wrap the extracted, scanned content in XML-style boundary tags before returning. The wrapping SHALL occur after all scanning (request guard and response guard) completes. The wrapped form SHALL be stored in `result.content`; the unwrapped markdown SHALL be stored in `result.raw_content`.

The opening tag format:
```
<web_content untrusted="true" source="{html-escaped URL}" fetched_at="{ISO 8601 UTC}" marker="{nonce}">
```

The closing tag format:
```
</web_content marker="{same nonce}">
```

The `source` and `fetched_at` attributes SHALL be HTML-escaped (replacing `&`, `"`, `<`, `>` with their XML entities).

#### Scenario: Wrapped content has matching nonces
- **WHEN** `safe_fetch()` succeeds
- **THEN** the nonce in `<web_content marker="...">` equals the nonce in `</web_content marker="...">` and both equal `result.content_marker`

#### Scenario: Source URL is included in opening tag
- **WHEN** `safe_fetch("https://example.com/page")` succeeds
- **THEN** `result.content` contains `source="https://example.com/page"` (or the final redirect URL) in the opening tag

#### Scenario: fetched_at is an ISO 8601 UTC timestamp
- **WHEN** `safe_fetch()` succeeds
- **THEN** `result.content` contains `fetched_at="YYYY-MM-DDTHH:MM:SSZ"` in the opening tag

#### Scenario: URLs with special characters are escaped
- **WHEN** the final URL contains `&` (e.g., `https://example.com/?a=1&b=2`)
- **THEN** the `source` attribute value contains `&amp;` in place of `&`

#### Scenario: raw_content is the unwrapped markdown
- **WHEN** `safe_fetch()` succeeds
- **THEN** `result.raw_content` equals the markdown content without any boundary tags

### Requirement: Injected content cannot forge closing tag
The nonce-based closing tag design SHALL make it computationally infeasible for content injected into the fetched page to produce a valid closing tag. The nonce SHALL be generated after the HTTP response is received, making it unknown to the remote server at page-generation time.

#### Scenario: Nonce is generated after fetch, not before
- **WHEN** the wrapping step runs
- **THEN** the nonce has been generated in the same `safe_fetch()` call, after the HTTP response was obtained — it cannot have been predicted by the server
