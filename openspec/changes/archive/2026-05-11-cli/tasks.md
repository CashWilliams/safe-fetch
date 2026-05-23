## 1. Entry Point Wiring

- [x] 1.1 Add `[project.scripts]` entry point to `pyproject.toml`: `safe-fetch = "safe_fetch._cli:main"`
- [x] 1.2 Create `safe_fetch/_cli.py` with a `main()` stub and `if __name__ == "__main__": main()`

## 2. Environment Variable Config Loading

- [x] 2.1 Implement `_load_config()` that reads all `SAFE_FETCH_*` env vars and returns a `SafeFetchConfig`
- [x] 2.2 Parse `SAFE_FETCH_REQUEST_POLICY` and `SAFE_FETCH_RESPONSE_POLICY` (accept `strict`/`warn`/`permissive`, case-insensitive; exit 1 on invalid value)
- [x] 2.3 Parse `SAFE_FETCH_CONNECT_TIMEOUT` and `SAFE_FETCH_READ_TIMEOUT` as floats; exit 1 on non-numeric value
- [x] 2.4 Parse `SAFE_FETCH_USER_AGENT` as string; fall through to default if unset
- [x] 2.5 `llm_client` is always `None` in CLI context (LLM escalation is Python-API-only)

## 3. Argument Parser

- [x] 3.1 Build `argparse.ArgumentParser` with `formatter_class=argparse.RawDescriptionHelpFormatter` and a one-line description
- [x] 3.2 Add positional `url` argument; if missing, print help to stderr and exit 1
- [x] 3.3 Add `--json` boolean flag
- [x] 3.4 Write verbose `--help` epilog containing: env var reference table (name, default, accepted values), three usage examples (basic fetch, `--json`, env var config), and exit code table (codes 0–8)

## 4. Core CLI Logic

- [x] 4.1 Call `_load_config()` at startup to build `SafeFetchConfig`
- [x] 4.2 Call `asyncio.run(safe_fetch(url, config))` and capture `SafeFetchResult`
- [x] 4.3 Default output: print `result.content` to stdout; if content is empty, print error to stderr and exit 7
- [x] 4.4 `--json` output: serialize full `SafeFetchResult` to JSON (findings as dicts) and print to stdout

## 5. Exit Code Handling

- [x] 5.1 Define exit code constants mapping each `SafeFetchError` subclass to its code (2–8)
- [x] 5.2 Wrap fetch call in try/except for each `SafeFetchError` subclass; print message to stderr and `sys.exit(code)`
- [x] 5.3 Under `--json`, catch errors and emit `{"error": "<ClassName>", "message": "<str>"}` to stdout before exiting non-zero

## 6. Tests

- [x] 6.1 Create `tests/test_cli.py`; test `_load_config()` reads env vars correctly and applies defaults
- [x] 6.2 Test invalid env var value (`SAFE_FETCH_REQUEST_POLICY=banana`) exits 1
- [x] 6.3 Test `--json` success output is valid JSON with all `SafeFetchResult` fields
- [x] 6.4 Test `--json` error output on `SSRFBlockedError` (exit 3, JSON on stdout)
- [x] 6.5 Test exit code 2 for `InvalidSchemeError` (`file://` URL)
- [x] 6.6 Test exit code 3 for `SSRFBlockedError` (private IP)
- [x] 6.7 Test empty content exits 7
- [x] 6.8 Test `safe-fetch --help` exits 0 and output contains env var table and exit code table
