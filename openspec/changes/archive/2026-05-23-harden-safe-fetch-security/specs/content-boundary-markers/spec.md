## MODIFIED Requirements

### Requirement: Content boundary wrapping
`safe_fetch()` SHALL wrap the safe, scanned content in XML-style boundary tags before returning. The wrapping SHALL occur after request guard, fetch pipeline, response guard, safe Markdown transformation, and metadata redaction complete. The wrapped form SHALL be stored in `result.content`; the unwrapped safe Markdown SHALL be stored in `result.safe_content`; the pre-transform Markdown SHALL be stored in `result.raw_content`.

The opening tag format:
```
<web_content untrusted="true" source="{html-escaped redacted URL}" fetched_at="{ISO 8601 UTC}" marker="{nonce}">
```

The closing tag format:
```
</web_content marker="{same nonce}">
```

The `source` and `fetched_at` attributes SHALL be HTML-escaped (replacing `&`, `"`, `<`, `>` with their XML entities). The `source` attribute SHALL use a redacted URL that does not expose secrets or PII.

#### Scenario: Wrapped content has matching nonces
- **WHEN** `safe_fetch()` succeeds
- **THEN** the nonce in `<web_content marker="...">` equals the nonce in `</web_content marker="...">` and both equal `result.content_marker`

#### Scenario: Redacted source URL is included in opening tag
- **WHEN** `safe_fetch("https://example.com/page?token=secret")` succeeds under permissive leak policy
- **THEN** `result.content` contains the final source URL with the token value redacted in the opening tag

#### Scenario: fetched_at is an ISO 8601 UTC timestamp
- **WHEN** `safe_fetch()` succeeds
- **THEN** `result.content` contains `fetched_at="YYYY-MM-DDTHH:MM:SSZ"` in the opening tag

#### Scenario: URLs with special characters are escaped
- **WHEN** the redacted final URL contains `&`
- **THEN** the `source` attribute value contains `&amp;` in place of `&`

#### Scenario: safe_content is the unwrapped wrapped body
- **WHEN** `safe_fetch()` succeeds
- **THEN** `result.safe_content` equals the Markdown body inside the boundary tags without wrapping
