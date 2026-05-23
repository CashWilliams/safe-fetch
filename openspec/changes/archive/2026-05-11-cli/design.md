## Context

`safe-fetch` is an async Python library. Its public API is `await safe_fetch(url, config)`. To be usable as an AI agent tool — where the agent invokes a shell command and reads stdout — it needs a synchronous CLI wrapper that drives `asyncio.run()`, formats output for machine consumption, and exits with meaningful codes.

The CLI is a **call tool, not a config tool.** Security posture (policy, timeouts, headers) is set by the operator at deploy time via environment variables. An agent invoking the CLI cannot change these settings per-call. This is intentional: an agent that could pass `--policy permissive` to bypass injection detection would defeat the purpose of the library.

## Goals / Non-Goals

**Goals:**
- Single entry point `safe-fetch <url>` runnable via `uv run safe-fetch` today, system-installable later
- Stdout is either clean markdown (default) or JSON (`--json`) — both agent-readable
- Config loaded from environment variables at startup — no per-invocation config flags
- Verbose `--help`: flag descriptions, examples, env var reference, and exit code table
- Meaningful exit codes so agents can branch on failure type without parsing stderr
- No new runtime dependencies (argparse is stdlib)

**Non-Goals:**
- Per-invocation policy, timeout, or header overrides — config is operator-controlled
- Interactive mode, pagination, or terminal colors
- Persistent config file — env vars are sufficient for v1
- Piping URLs from stdin — one URL per invocation matches agent tool-call model
- LLM escalation from CLI — requires a live SDK object; CLI runs with MEDIUM findings staying MEDIUM
- POST or other HTTP methods — GET only, matching the library

## Decisions

### 1. `argparse` over `click` or `typer`

**Decision:** Use `argparse` (stdlib).

**Rationale:** Zero new dependencies. The CLI is thin — one positional arg and two flags. `argparse` `formatter_class=RawDescriptionHelpFormatter` gives full control over `--help` layout, enabling the verbose exit-code table, examples block, and env var reference. `click`/`typer` add install overhead not worth it for this surface area.

**Alternatives considered:** `typer` generates nicer help automatically but requires an extra dep; `click` same.

### 2. Configuration via environment variables

**Decision:** All `SafeFetchConfig` knobs are read from env vars at CLI startup. No config flags on the CLI itself.

| Env var | Maps to | Default |
|---|---|---|
| `SAFE_FETCH_REQUEST_POLICY` | `request_policy` | `strict` |
| `SAFE_FETCH_RESPONSE_POLICY` | `response_policy` | `warn` |
| `SAFE_FETCH_CONNECT_TIMEOUT` | `connect_timeout` | `10.0` |
| `SAFE_FETCH_READ_TIMEOUT` | `read_timeout` | `30.0` |
| `SAFE_FETCH_USER_AGENT` | `user_agent` | `safe-fetch/1.0 (LLM-agent)` |

**Rationale:** Env vars are the standard mechanism for configuring tools in agent environments (systemd units, Docker, process supervisors). They allow operators to lock down policy without touching CLI arguments. An agent invoking the command cannot see or change env vars set in the parent process by the operator.

**Alternatives considered:** Config file (`~/.config/safe-fetch/config.toml`) — adds file management complexity for v1. CLI flags — explicitly rejected; agents could override security policy.

### 3. Exit code scheme

**Decision:** Map each `SafeFetchError` subclass to a distinct exit code.

| Code | Meaning |
|---|---|
| 0 | Success |
| 1 | Generic / unexpected error |
| 2 | `InvalidSchemeError` |
| 3 | `SSRFBlockedError` |
| 4 | `SecretLeakError` |
| 5 | `PIILeakError` |
| 6 | `FetchTimeoutError` |
| 7 | `ExtractionFailedError` (includes empty/no content) |
| 8 | `InjectionDetectedError` |

**Rationale:** Distinct codes let an agent react differently to SSRF (security signal — abort), timeout (retry), or injection (content threat — escalate) without text parsing. Exit 7 also covers the case where fetch succeeds but content is empty — no silent empty stdout.

**Alternatives considered:** POSIX-style 0/1 only — too coarse for agent use.

### 4. Output format

**Decision:** Default stdout is the raw markdown content. `--json` emits a single JSON object with all `SafeFetchResult` fields. Errors always go to stderr + non-zero exit, never to stdout — stdout is always either content or empty on error.

Under `--json`, errors emit `{"error": "<ClassName>", "message": "<str>"}` to stdout so agents capturing only stdout still get structured error info.

**Rationale:** Agents read stdout. Default markdown is immediately human-readable too. Keeping errors off stdout means agents can parse stdout unconditionally without checking for error shapes in the content stream.

### 5. LLM escalation

**Decision:** CLI always runs without `llm_client` (i.e., `llm_client=None`). MEDIUM confidence injection findings stay MEDIUM; no escalation API call is made.

**Rationale:** Wiring a live LLM SDK client requires instantiation logic that belongs in application code, not a CLI. Operators who need LLM escalation should use the Python API directly. The WARN policy (default) will still log and redact MEDIUM findings; STRICT will not raise on them (only HIGH triggers raise).

### 6. Async bridging via `asyncio.run()`

**Decision:** `main()` is synchronous; it calls `asyncio.run(safe_fetch(...))` internally.

**Rationale:** `[project.scripts]` entry points must be sync. `asyncio.run()` is the standard bridge for a fresh process invocation.

## Risks / Trade-offs

- **Env var misconfiguration** → Operator sets `SAFE_FETCH_REQUEST_POLICY=permissive` and forgets. Mitigated by documenting defaults prominently in `--help` and printing active config in verbose mode.
- **Large responses on stdout** → No pagination. Agents handle large stdout. Read timeout (`SAFE_FETCH_READ_TIMEOUT`) bounds response time indirectly.
- **JSON field stability** → `SafeFetchResult` fields are a de-facto CLI contract under `--json`. Adding fields is safe; removing or renaming is breaking. Note in `--help`.
- **MEDIUM findings not escalated** → Accepted trade-off. Operators requiring LLM escalation use the Python API.
