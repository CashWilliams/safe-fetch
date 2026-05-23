"""Tests for the safe-fetch CLI."""
from __future__ import annotations

import json
import subprocess
import sys
from dataclasses import dataclass, field
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from safe_fetch._cli import _load_config, main
from safe_fetch._exceptions import (
    HTTPStatusError,
    InjectionDetectedError,
    InvalidSchemeError,
    Policy,
    RedirectLimitError,
    ResponseTooLargeError,
    SSRFBlockedError,
)
from safe_fetch._types import InjectionFinding, RequestFinding, SafeFetchConfig, SafeFetchResult


# ---------------------------------------------------------------------------
# 6.1 _load_config reads env vars and applies defaults
# ---------------------------------------------------------------------------

def test_load_config_defaults(monkeypatch):
    for var in (
        "SAFE_FETCH_REQUEST_POLICY",
        "SAFE_FETCH_RESPONSE_POLICY",
        "SAFE_FETCH_CONNECT_TIMEOUT",
        "SAFE_FETCH_READ_TIMEOUT",
        "SAFE_FETCH_USER_AGENT",
    ):
        monkeypatch.delenv(var, raising=False)

    cfg = _load_config()
    assert cfg.request_policy == Policy.STRICT
    assert cfg.response_policy == Policy.WARN
    assert cfg.connect_timeout == 10.0
    assert cfg.read_timeout == 30.0
    assert cfg.user_agent == "safe-fetch/1.0 (LLM-agent)"
    assert cfg.llm_client is None
    assert cfg.max_response_bytes == 10_000_000
    assert cfg.total_timeout == 60.0
    assert cfg.max_redirects == 5
    assert cfg.safe_markdown is True


def test_load_config_reads_env_vars(monkeypatch):
    monkeypatch.setenv("SAFE_FETCH_REQUEST_POLICY", "permissive")
    monkeypatch.setenv("SAFE_FETCH_RESPONSE_POLICY", "STRICT")
    monkeypatch.setenv("SAFE_FETCH_CONNECT_TIMEOUT", "5.5")
    monkeypatch.setenv("SAFE_FETCH_READ_TIMEOUT", "60")
    monkeypatch.setenv("SAFE_FETCH_USER_AGENT", "my-agent/2.0")
    monkeypatch.setenv("SAFE_FETCH_MAX_RESPONSE_BYTES", "1024")
    monkeypatch.setenv("SAFE_FETCH_TOTAL_TIMEOUT", "9.5")
    monkeypatch.setenv("SAFE_FETCH_MAX_REDIRECTS", "2")
    monkeypatch.setenv("SAFE_FETCH_ALLOW_HTTP", "false")
    monkeypatch.setenv("SAFE_FETCH_ALLOWED_HOSTS", "docs.example.com,api.example.com")
    monkeypatch.setenv("SAFE_FETCH_BLOCKED_CIDRS", "10.0.0.0/8")
    monkeypatch.setenv("SAFE_FETCH_ALLOWED_CONTENT_TYPES", "text/plain,text/markdown")
    monkeypatch.setenv("SAFE_FETCH_HTTP_STATUS_POLICY", "all")
    monkeypatch.setenv("SAFE_FETCH_REDACTION_MODE", "document")
    monkeypatch.setenv("SAFE_FETCH_SAFE_MARKDOWN", "false")
    monkeypatch.setenv("SAFE_FETCH_CLASSIFIER_TIMEOUT", "1.5")
    monkeypatch.setenv("SAFE_FETCH_CLASSIFIER_FAILURE_POLICY", "strict")

    cfg = _load_config()
    assert cfg.request_policy == Policy.PERMISSIVE
    assert cfg.response_policy == Policy.STRICT
    assert cfg.connect_timeout == 5.5
    assert cfg.read_timeout == 60.0
    assert cfg.user_agent == "my-agent/2.0"
    assert cfg.llm_client is None
    assert cfg.max_response_bytes == 1024
    assert cfg.total_timeout == 9.5
    assert cfg.max_redirects == 2
    assert cfg.allow_http is False
    assert cfg.allowed_hosts == {"docs.example.com", "api.example.com"}
    assert cfg.blocked_cidrs == {"10.0.0.0/8"}
    assert cfg.allowed_content_types == {"text/plain", "text/markdown"}
    assert cfg.http_status_policy == "all"
    assert cfg.redaction_mode == "document"
    assert cfg.safe_markdown is False
    assert cfg.classifier_timeout == 1.5
    assert cfg.classifier_failure_policy == Policy.STRICT


# ---------------------------------------------------------------------------
# 6.2 Invalid env var value exits 1
# ---------------------------------------------------------------------------

def test_load_config_invalid_policy_exits_1(monkeypatch):
    monkeypatch.setenv("SAFE_FETCH_REQUEST_POLICY", "banana")
    with pytest.raises(SystemExit) as exc_info:
        _load_config()
    assert exc_info.value.code == 1


def test_load_config_invalid_timeout_exits_1(monkeypatch):
    monkeypatch.setenv("SAFE_FETCH_CONNECT_TIMEOUT", "not-a-number")
    with pytest.raises(SystemExit) as exc_info:
        _load_config()
    assert exc_info.value.code == 1


def test_load_config_invalid_cidr_exits_1(monkeypatch):
    monkeypatch.setenv("SAFE_FETCH_BLOCKED_CIDRS", "not-a-cidr")
    with pytest.raises(SystemExit) as exc_info:
        _load_config()
    assert exc_info.value.code == 1


def test_load_config_invalid_boolean_exits_1(monkeypatch):
    monkeypatch.setenv("SAFE_FETCH_SAFE_MARKDOWN", "maybe")
    with pytest.raises(SystemExit) as exc_info:
        _load_config()
    assert exc_info.value.code == 1


# ---------------------------------------------------------------------------
# Helper: build a mock SafeFetchResult
# ---------------------------------------------------------------------------

def _make_result(**kwargs):
    defaults = dict(
        content='<web_content untrusted="true" source="https://example.com" fetched_at="2026-05-11T00:00:00Z" marker="abc123">\n# Hello\n\nWorld\n</web_content marker="abc123">',
        raw_content="# Hello\n\nWorld",
        content_marker="abc123",
        url="https://example.com",
        status_code=200,
        extraction_method="trafilatura",
        request_findings=[],
        response_findings=[],
    )
    defaults.update(kwargs)
    return SafeFetchResult(**defaults)


# ---------------------------------------------------------------------------
# 6.3 --json success output is valid JSON with all SafeFetchResult fields
# ---------------------------------------------------------------------------

def test_json_success_output(monkeypatch, capsys):
    result = _make_result()

    def run_success(coro):
        coro.close()
        return result

    monkeypatch.setattr("safe_fetch._cli.asyncio.run", run_success)
    monkeypatch.setattr(
        "sys.argv", ["safe-fetch", "--json", "https://example.com"]
    )
    # Patch _load_config to avoid reading env vars
    monkeypatch.setattr("safe_fetch._cli._load_config", lambda: SafeFetchConfig())

    main()

    captured = capsys.readouterr()
    data = json.loads(captured.out)
    assert "content" in data
    assert "url" in data
    assert "status_code" in data
    assert "extraction_method" in data
    assert "request_findings" in data
    assert "response_findings" in data


# ---------------------------------------------------------------------------
# 6.4 --json error output on SSRFBlockedError (exit 3, JSON on stdout)
# ---------------------------------------------------------------------------

def test_json_ssrf_error(monkeypatch, capsys):
    def raise_ssrf(coro):
        coro.close()
        raise SSRFBlockedError("Private IP blocked")

    monkeypatch.setattr("safe_fetch._cli.asyncio.run", raise_ssrf)
    monkeypatch.setattr("sys.argv", ["safe-fetch", "--json", "http://192.168.1.1/"])
    monkeypatch.setattr("safe_fetch._cli._load_config", lambda: SafeFetchConfig())

    with pytest.raises(SystemExit) as exc_info:
        main()

    assert exc_info.value.code == 3
    captured = capsys.readouterr()
    data = json.loads(captured.out)
    assert data["error"] == "SSRFBlockedError"
    assert "message" in data


# ---------------------------------------------------------------------------
# 6.5 Exit code 2 for InvalidSchemeError (file:// URL)
# ---------------------------------------------------------------------------

def test_exit_code_invalid_scheme(monkeypatch, capsys):
    def raise_invalid(coro):
        coro.close()
        raise InvalidSchemeError("file:// not allowed")

    monkeypatch.setattr("safe_fetch._cli.asyncio.run", raise_invalid)
    monkeypatch.setattr("sys.argv", ["safe-fetch", "file:///etc/passwd"])
    monkeypatch.setattr("safe_fetch._cli._load_config", lambda: SafeFetchConfig())

    with pytest.raises(SystemExit) as exc_info:
        main()

    assert exc_info.value.code == 2


# ---------------------------------------------------------------------------
# 6.6 Exit code 3 for SSRFBlockedError (private IP)
# ---------------------------------------------------------------------------

def test_exit_code_ssrf(monkeypatch, capsys):
    def raise_ssrf(coro):
        coro.close()
        raise SSRFBlockedError("Private IP blocked")

    monkeypatch.setattr("safe_fetch._cli.asyncio.run", raise_ssrf)
    monkeypatch.setattr("sys.argv", ["safe-fetch", "http://192.168.1.1/"])
    monkeypatch.setattr("safe_fetch._cli._load_config", lambda: SafeFetchConfig())

    with pytest.raises(SystemExit) as exc_info:
        main()

    assert exc_info.value.code == 3


def test_exit_code_redirect_limit(monkeypatch, capsys):
    def raise_redirect_limit(coro):
        coro.close()
        raise RedirectLimitError("Too many redirects", redirects=6)

    monkeypatch.setattr("safe_fetch._cli.asyncio.run", raise_redirect_limit)
    monkeypatch.setattr("sys.argv", ["safe-fetch", "https://example.com/loop"])
    monkeypatch.setattr("safe_fetch._cli._load_config", lambda: SafeFetchConfig())

    with pytest.raises(SystemExit) as exc_info:
        main()

    assert exc_info.value.code == 9


def test_exit_code_response_too_large(monkeypatch, capsys):
    def raise_too_large(coro):
        coro.close()
        raise ResponseTooLargeError("too large")

    monkeypatch.setattr("safe_fetch._cli.asyncio.run", raise_too_large)
    monkeypatch.setattr("sys.argv", ["safe-fetch", "https://example.com/"])
    monkeypatch.setattr("safe_fetch._cli._load_config", lambda: SafeFetchConfig())

    with pytest.raises(SystemExit) as exc_info:
        main()

    assert exc_info.value.code == 12


def test_exit_code_http_status(monkeypatch, capsys):
    def raise_status(coro):
        coro.close()
        raise HTTPStatusError("bad status")

    monkeypatch.setattr("safe_fetch._cli.asyncio.run", raise_status)
    monkeypatch.setattr("sys.argv", ["safe-fetch", "https://example.com/"])
    monkeypatch.setattr("safe_fetch._cli._load_config", lambda: SafeFetchConfig())

    with pytest.raises(SystemExit) as exc_info:
        main()

    assert exc_info.value.code == 14


# ---------------------------------------------------------------------------
# 6.7 Test empty content exits 7
# ---------------------------------------------------------------------------

def test_empty_content_exits_7(monkeypatch, capsys):
    result = _make_result(content="", raw_content="", content_marker="abc123")

    def run_success(coro):
        coro.close()
        return result

    monkeypatch.setattr("safe_fetch._cli.asyncio.run", run_success)
    monkeypatch.setattr("sys.argv", ["safe-fetch", "https://example.com"])
    monkeypatch.setattr("safe_fetch._cli._load_config", lambda: SafeFetchConfig())

    with pytest.raises(SystemExit) as exc_info:
        main()

    assert exc_info.value.code == 7
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "error" in captured.err


# ---------------------------------------------------------------------------
# 6.8 safe-fetch --help exits 0 and contains env var table and exit code table
# ---------------------------------------------------------------------------

def test_help_exits_0_and_contains_tables():
    result = subprocess.run(
        [sys.executable, "-m", "safe_fetch._cli", "--help"],
        capture_output=True,
        text=True,
    )
    # argparse prints help and exits 0
    assert result.returncode == 0
    output = result.stdout
    # env var table
    assert "SAFE_FETCH_REQUEST_POLICY" in output
    assert "SAFE_FETCH_RESPONSE_POLICY" in output
    assert "SAFE_FETCH_CONNECT_TIMEOUT" in output
    assert "SAFE_FETCH_READ_TIMEOUT" in output
    assert "SAFE_FETCH_USER_AGENT" in output
    assert "SAFE_FETCH_MAX_RESPONSE_BYTES" in output
    assert "SAFE_FETCH_BLOCKED_CIDRS" in output
    assert "SAFE_FETCH_SAFE_MARKDOWN" in output
    # exit code table
    assert "InvalidSchemeError" in output
    assert "SSRFBlockedError" in output
    assert "InjectionDetectedError" in output
    assert "ResponseTooLargeError" in output
    assert "HTTPStatusError" in output
