## Why

AI agents interact with tools via shell commands, not Python imports. `safe-fetch` currently has no CLI entry point, making it unusable as an agent tool call or a composable Unix utility. Adding a thin CLI layer unlocks this without touching the existing Python API.

## What Changes

- New `safe_fetch/_cli.py` module implementing the CLI using `argparse`
- New `[project.scripts]` entry point in `pyproject.toml` wiring `safe-fetch = "safe_fetch._cli:main"`
- `uv run safe-fetch <url>` works immediately; `uv tool install` / `pipx install` will install it system-wide
- Python API (`await safe_fetch(url, config)`) is unchanged — CLI is purely additive

## Capabilities

### New Capabilities

- `cli`: Command-line interface — positional URL argument, `--request-policy` / `--response-policy` flags, `--json` structured output mode, `--connect-timeout` / `--read-timeout` overrides, `--user-agent`, verbose `--help` with flag descriptions, examples, and exit code reference

### Modified Capabilities

## Impact

- `pyproject.toml`: adds `[project.scripts]` entry point and `argparse` (stdlib, no new deps)
- `safe_fetch/_cli.py`: new file, ~150 lines
- No changes to `safe_fetch/__init__.py` or any existing module
- Tests: new `tests/test_cli.py` covering argument parsing and output format
