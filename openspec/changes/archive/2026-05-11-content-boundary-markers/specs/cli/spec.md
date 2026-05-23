## MODIFIED Requirements

### Requirement: JSON output mode
The CLI SHALL support a `--json` flag that emits a single JSON object to stdout containing all `SafeFetchResult` fields: `content` (wrapped), `raw_content` (plain markdown), `content_marker` (nonce), `url`, `status_code`, `extraction_method`, `request_findings`, and `response_findings`.

#### Scenario: --json emits structured result on success
- **WHEN** `safe-fetch --json https://example.com` succeeds
- **THEN** stdout is a valid JSON object with all `SafeFetchResult` fields including `raw_content` and `content_marker`; findings are JSON arrays

#### Scenario: --json errors emit JSON to stdout
- **WHEN** `safe-fetch --json <url>` fails with a `SafeFetchError`
- **THEN** stdout is `{"error": "<ClassName>", "message": "<str>"}` and exit code is non-zero
