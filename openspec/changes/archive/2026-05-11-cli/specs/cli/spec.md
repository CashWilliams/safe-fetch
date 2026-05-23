## ADDED Requirements

### Requirement: URL positional argument
The CLI SHALL accept a single positional URL argument and fetch it using `safe_fetch()`. Running with no URL argument SHALL print help and exit 1.

#### Scenario: Valid URL is fetched and content printed
- **WHEN** `safe-fetch https://example.com` is run
- **THEN** the fetched markdown content is printed to stdout and the process exits 0

#### Scenario: Missing URL prints help
- **WHEN** `safe-fetch` is run with no arguments
- **THEN** the help text is printed to stderr and the process exits 1

#### Scenario: Empty content exits with code 7
- **WHEN** the fetch succeeds but returns empty or no extractable content
- **THEN** an error message is printed to stderr and the process exits 7 (same as `ExtractionFailedError`)

### Requirement: Configuration via environment variables
The CLI SHALL read all `SafeFetchConfig` knobs exclusively from environment variables. No per-invocation config flags SHALL be exposed. This ensures operators control security posture and agents cannot override it.

| Env var | Config field | Default |
|---|---|---|
| `SAFE_FETCH_REQUEST_POLICY` | `request_policy` | `strict` |
| `SAFE_FETCH_RESPONSE_POLICY` | `response_policy` | `warn` |
| `SAFE_FETCH_CONNECT_TIMEOUT` | `connect_timeout` | `10.0` |
| `SAFE_FETCH_READ_TIMEOUT` | `read_timeout` | `30.0` |
| `SAFE_FETCH_USER_AGENT` | `user_agent` | `safe-fetch/1.0 (LLM-agent)` |

#### Scenario: Env vars configure policy at startup
- **WHEN** `SAFE_FETCH_REQUEST_POLICY=permissive safe-fetch <url>` is run
- **THEN** the underlying `SafeFetchConfig` uses `request_policy=Policy.PERMISSIVE`

#### Scenario: Defaults apply when env vars are absent
- **WHEN** no `SAFE_FETCH_*` env vars are set
- **THEN** `SafeFetchConfig()` defaults are used: STRICT request policy, WARN response policy

#### Scenario: Invalid env var value exits with error
- **WHEN** `SAFE_FETCH_REQUEST_POLICY=banana safe-fetch <url>` is run
- **THEN** an error is printed to stderr and the process exits 1

### Requirement: JSON output mode
The CLI SHALL support a `--json` flag that emits a single JSON object to stdout containing all `SafeFetchResult` fields: `content`, `url`, `status_code`, `extraction_method`, `request_findings`, and `response_findings`.

#### Scenario: --json emits structured result on success
- **WHEN** `safe-fetch --json https://example.com` succeeds
- **THEN** stdout is a valid JSON object with all `SafeFetchResult` fields; findings are JSON arrays

#### Scenario: --json errors emit JSON to stdout
- **WHEN** `safe-fetch --json <url>` fails with a `SafeFetchError`
- **THEN** stdout is `{"error": "<ClassName>", "message": "<str>"}` and exit code is non-zero

### Requirement: Exit codes
The CLI SHALL exit with a distinct non-zero code for each `SafeFetchError` subclass. Exit 0 SHALL only occur on success with non-empty content.

| Code | Meaning |
|---|---|
| 0 | Success |
| 1 | Generic / unexpected error or bad arguments |
| 2 | `InvalidSchemeError` |
| 3 | `SSRFBlockedError` |
| 4 | `SecretLeakError` |
| 5 | `PIILeakError` |
| 6 | `FetchTimeoutError` |
| 7 | `ExtractionFailedError` or empty content |
| 8 | `InjectionDetectedError` |

#### Scenario: SSRF block exits with code 3
- **WHEN** `safe-fetch http://192.168.1.1/` is run
- **THEN** an error message is printed to stderr and the process exits 3

#### Scenario: Invalid scheme exits with code 2
- **WHEN** `safe-fetch file:///etc/passwd` is run
- **THEN** an error message is printed to stderr and the process exits 2

#### Scenario: Timeout exits with code 6
- **WHEN** the fetch times out
- **THEN** stderr includes the timeout phase and the process exits 6

#### Scenario: Injection detected exits with code 8
- **WHEN** `SAFE_FETCH_RESPONSE_POLICY=strict` is set and fetched content triggers injection detection
- **THEN** the process exits 8

### Requirement: Verbose --help
The CLI `--help` SHALL include: a one-line description, `--json` flag description, all env var names with their defaults, at least three usage examples, and the full exit code table.

#### Scenario: --help includes env var reference
- **WHEN** `safe-fetch --help` is run
- **THEN** stdout lists all `SAFE_FETCH_*` env vars with their defaults and accepted values

#### Scenario: --help includes exit code table
- **WHEN** `safe-fetch --help` is run
- **THEN** stdout includes a table mapping exit codes 0–8 to their meanings

#### Scenario: --help includes usage examples
- **WHEN** `safe-fetch --help` is run
- **THEN** stdout includes examples for basic fetch, `--json` mode, and env var configuration

### Requirement: Script entry point
The `safe-fetch` command SHALL be declared in `[project.scripts]` in `pyproject.toml` as `safe-fetch = "safe_fetch._cli:main"`. It SHALL be runnable via `uv run safe-fetch` without global installation, and installable system-wide via `uv tool install` or `pipx install`.

#### Scenario: uv run safe-fetch works without global install
- **WHEN** `uv run safe-fetch --help` is run from the project directory
- **THEN** the help text is printed and the process exits 0

#### Scenario: Python API is unchanged
- **WHEN** a caller imports `safe_fetch`
- **THEN** the existing Python API (`safe_fetch()`, `SafeFetchConfig`, etc.) is unchanged; `_cli` is an internal module
