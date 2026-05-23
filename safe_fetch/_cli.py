"""Command-line interface for safe-fetch."""
from __future__ import annotations

import argparse
import asyncio
import ipaddress
import json
import os
import sys
from dataclasses import asdict

from ._exceptions import (
    ExtractionFailedError,
    FetchTimeoutError,
    HTTPStatusError,
    HostPolicyError,
    InjectionDetectedError,
    InvalidSchemeError,
    InvalidURLError,
    PIILeakError,
    Policy,
    RedirectLimitError,
    ResponseTooLargeError,
    SSRFBlockedError,
    SafeFetchError,
    SecretLeakError,
    UnsupportedContentTypeError,
    ClassifierError,
)
from ._types import SafeFetchConfig

# Exit code constants
EXIT_SUCCESS = 0
EXIT_GENERIC = 1
EXIT_INVALID_SCHEME = 2
EXIT_SSRF_BLOCKED = 3
EXIT_SECRET_LEAK = 4
EXIT_PII_LEAK = 5
EXIT_TIMEOUT = 6
EXIT_EXTRACTION_FAILED = 7
EXIT_INJECTION_DETECTED = 8
EXIT_REDIRECT_LIMIT = 9
EXIT_INVALID_URL = 10
EXIT_HOST_POLICY = 11
EXIT_RESPONSE_TOO_LARGE = 12
EXIT_UNSUPPORTED_CONTENT_TYPE = 13
EXIT_HTTP_STATUS = 14
EXIT_CLASSIFIER = 15

_ERROR_CODES: dict[type[SafeFetchError], int] = {
    InvalidSchemeError: EXIT_INVALID_SCHEME,
    SSRFBlockedError: EXIT_SSRF_BLOCKED,
    SecretLeakError: EXIT_SECRET_LEAK,
    PIILeakError: EXIT_PII_LEAK,
    FetchTimeoutError: EXIT_TIMEOUT,
    ExtractionFailedError: EXIT_EXTRACTION_FAILED,
    InjectionDetectedError: EXIT_INJECTION_DETECTED,
    RedirectLimitError: EXIT_REDIRECT_LIMIT,
    InvalidURLError: EXIT_INVALID_URL,
    HostPolicyError: EXIT_HOST_POLICY,
    ResponseTooLargeError: EXIT_RESPONSE_TOO_LARGE,
    UnsupportedContentTypeError: EXIT_UNSUPPORTED_CONTENT_TYPE,
    HTTPStatusError: EXIT_HTTP_STATUS,
    ClassifierError: EXIT_CLASSIFIER,
}

_EPILOG = """\
Environment Variables:
  SAFE_FETCH_REQUEST_POLICY   Request policy. Default: strict
                              Accepted: strict, warn, permissive
  SAFE_FETCH_RESPONSE_POLICY  Response policy. Default: warn
                              Accepted: strict, warn, permissive
  SAFE_FETCH_CONNECT_TIMEOUT  Connect timeout in seconds. Default: 10.0
  SAFE_FETCH_READ_TIMEOUT     Read timeout in seconds. Default: 30.0
  SAFE_FETCH_TOTAL_TIMEOUT    Full-operation timeout in seconds. Default: 60.0
  SAFE_FETCH_MAX_RESPONSE_BYTES Maximum response bytes. Default: 10000000
  SAFE_FETCH_MAX_REDIRECTS    Maximum redirect hops. Default: 5
  SAFE_FETCH_MAX_EXTRACTION_WORKERS Extraction worker limit. Default: 4
  SAFE_FETCH_ALLOW_HTTP       Allow http:// URLs. Default: true
  SAFE_FETCH_ALLOWED_HOSTS    Comma-separated exact allowed hosts
  SAFE_FETCH_ALLOWED_HOST_SUFFIXES Comma-separated allowed host suffixes
  SAFE_FETCH_BLOCKED_HOSTS    Comma-separated blocked hosts
  SAFE_FETCH_BLOCKED_CIDRS    Comma-separated blocked CIDRs
  SAFE_FETCH_ALLOWED_CIDRS    Comma-separated allowed CIDRs
  SAFE_FETCH_ALLOWED_CONTENT_TYPES Comma-separated content types
  SAFE_FETCH_HTTP_STATUS_POLICY Status policy: 2xx, 2xx,4xx, 2xx,3xx, all
  SAFE_FETCH_REDACTION_MODE   none, pattern, snippet, segment, document
  SAFE_FETCH_SAFE_MARKDOWN    Enable safe Markdown output. Default: true
  SAFE_FETCH_CLASSIFIER_TIMEOUT Classifier timeout seconds. Default: 5.0
  SAFE_FETCH_CLASSIFIER_FAILURE_POLICY Classifier failure policy. Default: warn
  SAFE_FETCH_USER_AGENT       User-Agent header. Default: safe-fetch/1.0 (LLM-agent)

Examples:
  # Basic fetch — prints markdown to stdout
  safe-fetch https://example.com

  # Structured JSON output
  safe-fetch --json https://example.com

  # Override response policy via env var
  SAFE_FETCH_RESPONSE_POLICY=strict safe-fetch https://example.com

Exit Codes:
  0  Success
  1  Generic / unexpected error or bad arguments
  2  InvalidSchemeError  — URL scheme is not http/https
  3  SSRFBlockedError    — URL resolves to private/reserved IP
  4  SecretLeakError     — secret detected in URL/headers
  5  PIILeakError        — PII detected in URL/headers
  6  FetchTimeoutError   — connect or read timeout
  7  ExtractionFailedError or empty content
  8  InjectionDetectedError — injection detected in response
  9  RedirectLimitError   — too many HTTP redirects
  10 InvalidURLError      — malformed, ambiguous, or unsafe URL
  11 HostPolicyError      — host or CIDR policy rejected target
  12 ResponseTooLargeError — response exceeded byte limit
  13 UnsupportedContentTypeError — content type is not allowed
  14 HTTPStatusError      — HTTP status policy rejected response
  15 ClassifierError      — classifier failed under strict failure policy

Note: --json field names in SafeFetchResult are stable; adding fields is safe
but renaming or removing fields is a breaking change.
"""


def _load_config() -> SafeFetchConfig:
    """Read SAFE_FETCH_* env vars and return a SafeFetchConfig."""
    kwargs: dict = {}

    def _parse_policy(var: str, default: Policy) -> Policy:
        raw = os.environ.get(var)
        if raw is None:
            return default
        try:
            return Policy(raw.lower())
        except ValueError:
            print(
                f"error: invalid value for {var}: {raw!r}. "
                f"Accepted: strict, warn, permissive",
                file=sys.stderr,
            )
            sys.exit(EXIT_GENERIC)

    kwargs["request_policy"] = _parse_policy(
        "SAFE_FETCH_REQUEST_POLICY", Policy.STRICT
    )
    kwargs["response_policy"] = _parse_policy(
        "SAFE_FETCH_RESPONSE_POLICY", Policy.WARN
    )

    for var, field in (
        ("SAFE_FETCH_CONNECT_TIMEOUT", "connect_timeout"),
        ("SAFE_FETCH_READ_TIMEOUT", "read_timeout"),
        ("SAFE_FETCH_TOTAL_TIMEOUT", "total_timeout"),
        ("SAFE_FETCH_CLASSIFIER_TIMEOUT", "classifier_timeout"),
    ):
        raw = os.environ.get(var)
        if raw is not None:
            try:
                kwargs[field] = float(raw)
            except ValueError:
                print(
                    f"error: invalid value for {var}: {raw!r}. "
                    f"Expected a number.",
                    file=sys.stderr,
                )
                sys.exit(EXIT_GENERIC)

    for var, field in (
        ("SAFE_FETCH_MAX_RESPONSE_BYTES", "max_response_bytes"),
        ("SAFE_FETCH_MAX_REDIRECTS", "max_redirects"),
        ("SAFE_FETCH_MAX_EXTRACTION_WORKERS", "max_extraction_workers"),
    ):
        raw = os.environ.get(var)
        if raw is not None:
            try:
                value = int(raw)
                if value < 1:
                    raise ValueError
                kwargs[field] = value
            except ValueError:
                print(
                    f"error: invalid value for {var}: {raw!r}. Expected a positive integer.",
                    file=sys.stderr,
                )
                sys.exit(EXIT_GENERIC)

    def _parse_bool(var: str) -> bool | None:
        raw = os.environ.get(var)
        if raw is None:
            return None
        value = raw.lower()
        if value in {"1", "true", "yes", "on"}:
            return True
        if value in {"0", "false", "no", "off"}:
            return False
        print(f"error: invalid value for {var}: {raw!r}. Expected a boolean.", file=sys.stderr)
        sys.exit(EXIT_GENERIC)

    allow_http = _parse_bool("SAFE_FETCH_ALLOW_HTTP")
    if allow_http is not None:
        kwargs["allow_http"] = allow_http
    safe_markdown = _parse_bool("SAFE_FETCH_SAFE_MARKDOWN")
    if safe_markdown is not None:
        kwargs["safe_markdown"] = safe_markdown

    def _parse_list(var: str) -> set[str] | None:
        raw = os.environ.get(var)
        if raw is None:
            return None
        return {item.strip() for item in raw.split(",") if item.strip()}

    for var, field in (
        ("SAFE_FETCH_ALLOWED_HOSTS", "allowed_hosts"),
        ("SAFE_FETCH_ALLOWED_HOST_SUFFIXES", "allowed_host_suffixes"),
        ("SAFE_FETCH_BLOCKED_HOSTS", "blocked_hosts"),
        ("SAFE_FETCH_ALLOWED_CONTENT_TYPES", "allowed_content_types"),
    ):
        values = _parse_list(var)
        if values is not None:
            kwargs[field] = values

    for var, field in (
        ("SAFE_FETCH_BLOCKED_CIDRS", "blocked_cidrs"),
        ("SAFE_FETCH_ALLOWED_CIDRS", "allowed_cidrs"),
    ):
        values = _parse_list(var)
        if values is not None:
            try:
                for value in values:
                    ipaddress.ip_network(value, strict=False)
            except ValueError:
                print(f"error: invalid value for {var}: {os.environ[var]!r}. Expected CIDRs.", file=sys.stderr)
                sys.exit(EXIT_GENERIC)
            kwargs[field] = values

    status_policy = os.environ.get("SAFE_FETCH_HTTP_STATUS_POLICY")
    if status_policy is not None:
        if status_policy.lower() not in {"2xx", "2xx,3xx", "2xx,4xx", "all"}:
            print("error: invalid value for SAFE_FETCH_HTTP_STATUS_POLICY", file=sys.stderr)
            sys.exit(EXIT_GENERIC)
        kwargs["http_status_policy"] = status_policy.lower()

    redaction_mode = os.environ.get("SAFE_FETCH_REDACTION_MODE")
    if redaction_mode is not None:
        if redaction_mode.lower() not in {"none", "pattern", "snippet", "segment", "document"}:
            print("error: invalid value for SAFE_FETCH_REDACTION_MODE", file=sys.stderr)
            sys.exit(EXIT_GENERIC)
        kwargs["redaction_mode"] = redaction_mode.lower()

    kwargs["classifier_failure_policy"] = _parse_policy(
        "SAFE_FETCH_CLASSIFIER_FAILURE_POLICY", Policy.WARN
    )

    user_agent = os.environ.get("SAFE_FETCH_USER_AGENT")
    if user_agent is not None:
        kwargs["user_agent"] = user_agent

    kwargs["llm_client"] = None

    return SafeFetchConfig(**kwargs)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="safe-fetch",
        description="Securely fetch web content for AI agents.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=_EPILOG,
    )
    parser.add_argument("url", nargs="?", help="URL to fetch")
    parser.add_argument(
        "--json",
        dest="json_output",
        action="store_true",
        default=False,
        help="Emit a JSON object with all SafeFetchResult fields instead of raw content.",
    )
    return parser


def main() -> None:
    from safe_fetch import safe_fetch

    parser = _build_parser()
    args = parser.parse_args()

    if not args.url:
        parser.print_help(sys.stderr)
        sys.exit(EXIT_GENERIC)

    config = _load_config()

    try:
        result = asyncio.run(safe_fetch(args.url, config))
    except SafeFetchError as exc:
        code = _ERROR_CODES.get(type(exc), EXIT_GENERIC)
        if args.json_output:
            print(
                json.dumps({"error": type(exc).__name__, "message": str(exc)}),
                flush=True,
            )
        else:
            print(f"error: {exc}", file=sys.stderr)
        sys.exit(code)
    except Exception as exc:
        if args.json_output:
            print(
                json.dumps({"error": type(exc).__name__, "message": str(exc)}),
                flush=True,
            )
        else:
            print(f"error: {exc}", file=sys.stderr)
        sys.exit(EXIT_GENERIC)

    if args.json_output:
        data = asdict(result)
        print(json.dumps(data), flush=True)
    else:
        if not result.raw_content:
            print("error: fetch succeeded but returned no extractable content", file=sys.stderr)
            sys.exit(EXIT_EXTRACTION_FAILED)
        print(result.content, end="")


if __name__ == "__main__":
    main()
