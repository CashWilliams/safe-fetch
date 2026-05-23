.PHONY: test lint typecheck security-audit

test:
	uv run pytest

lint:
	@if uv run ruff --version >/dev/null 2>&1; then uv run ruff check .; else echo "ruff is not installed; skipping lint"; fi

typecheck:
	@if uv run mypy --version >/dev/null 2>&1; then uv run mypy safe_fetch; else echo "mypy is not installed; skipping typecheck"; fi

security-audit:
	@if uv run pip-audit --version >/dev/null 2>&1; then uv run pip-audit; else echo "pip-audit is not installed; skipping security audit"; fi
