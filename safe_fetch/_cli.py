"""Command-line interface for safe-fetch."""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from dataclasses import asdict

from ._exceptions import (
    ExtractionFailedError,
    FetchTimeoutError,
    InjectionDetectedError,
    InvalidSchemeError,
    PIILeakError,
    Policy,
    SSRFBlockedError,
    SafeFetchError,
    SecretLeakError,
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

_ERROR_CODES: dict[type[SafeFetchError], int] = {
    InvalidSchemeError: EXIT_INVALID_SCHEME,
    SSRFBlockedError: EXIT_SSRF_BLOCKED,
    SecretLeakError: EXIT_SECRET_LEAK,
    PIILeakError: EXIT_PII_LEAK,
    FetchTimeoutError: EXIT_TIMEOUT,
    ExtractionFailedError: EXIT_EXTRACTION_FAILED,
    InjectionDetectedError: EXIT_INJECTION_DETECTED,
}

_EPILOG = """\
Environment Variables:
  SAFE_FETCH_REQUEST_POLICY   Request policy. Default: strict
                              Accepted: strict, warn, permissive
  SAFE_FETCH_RESPONSE_POLICY  Response policy. Default: warn
                              Accepted: strict, warn, permissive
  SAFE_FETCH_CONNECT_TIMEOUT  Connect timeout in seconds. Default: 10.0
  SAFE_FETCH_READ_TIMEOUT     Read timeout in seconds. Default: 30.0
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
