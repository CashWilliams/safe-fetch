"""Pre-request security scanning: secrets, PII, SSRF, scheme validation."""
from __future__ import annotations

import ipaddress
import logging
import re
import socket
from urllib.parse import parse_qsl, urlparse, unquote

from ._exceptions import (
    PIILeakError,
    Policy,
    SSRFBlockedError,
    SecretLeakError,
)
from ._types import RequestFinding
from ._types import SafeFetchConfig
from ._redaction import redacted_snippet, stable_hash
from ._url import canonicalize_url, enforce_ip_policy

log = logging.getLogger(__name__)

# PII regexes
_EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}")
_PHONE_RE = re.compile(
    r"(?:\+?1[-.\s]?)?(?:\(?\d{3}\)?[-.\s]?)?\d{3}[-.\s]?\d{4}"
    r"|\+\d{1,3}[-.\s]?\d{4,14}"
)
_SSN_RE = re.compile(r"\b(?!000|666|9\d{2})\d{3}[-]?(?!00)\d{2}[-]?(?!0000)\d{4}\b")
# Credit card: 13-19 digits, optionally space/dash separated
_CC_RAW_RE = re.compile(r"\b[\d][\d\s\-]{11,17}[\d]\b")


def _is_private_ip(addr: str) -> bool:
    try:
        ip = ipaddress.ip_address(addr)
    except ValueError:
        return False
    return not ip.is_global


def _luhn_valid(number: str) -> bool:
    digits = [int(d) for d in number if d.isdigit()]
    if len(digits) < 13 or len(digits) > 19:
        return False
    total = 0
    for i, d in enumerate(reversed(digits)):
        if i % 2 == 1:
            d *= 2
            if d > 9:
                d -= 9
        total += d
    return total % 10 == 0


def _scan_value_for_secrets(value: str, location: str) -> list[RequestFinding]:
    """Run detect-secrets detectors against a single string value."""
    findings: list[RequestFinding] = []
    try:
        from detect_secrets.plugins.aws import AWSKeyDetector
        from detect_secrets.plugins.base import BasePlugin
        from detect_secrets.plugins.github_token import GitHubTokenDetector
        from detect_secrets.plugins.high_entropy_strings import (
            Base64HighEntropyString,
            HexHighEntropyString,
        )
        from detect_secrets.plugins.keyword import KeywordDetector

        plugins: list[BasePlugin] = [
            AWSKeyDetector(),
            GitHubTokenDetector(),
            KeywordDetector(),
            HexHighEntropyString(hex_limit=3.0),
            Base64HighEntropyString(base64_limit=4.5),
        ]
        for plugin in plugins:
            for secret in plugin.analyze_line(filename="__value__", line=value, line_number=1):
                findings.append(
                    RequestFinding(
                        kind="secret",
                        detector=plugin.__class__.__name__,
                        location=location,
                        snippet=redacted_snippet(value),
                        stable_hash=stable_hash(value),
                    )
                )
                break  # one finding per plugin per value is enough
    except Exception:
        findings.extend(_keyword_secret_scan(value, location))
    return findings


def _keyword_secret_scan(value: str, location: str) -> list[RequestFinding]:
    """Simple keyword/entropy fallback for secret detection."""
    findings: list[RequestFinding] = []
    keywords = [
        "password", "passwd", "secret", "api_key", "apikey", "token",
        "auth", "credential", "private_key",
    ]
    lower = value.lower()
    for kw in keywords:
        if kw in lower and len(value) > 8:
            findings.append(
                RequestFinding(
                    kind="secret",
                    detector="KeywordDetector",
                    location=location,
                    snippet=redacted_snippet(value),
                    stable_hash=stable_hash(value),
                )
            )
            break
    # AWS key pattern
    if re.search(r"AKIA[0-9A-Z]{16}", value):
        findings.append(
            RequestFinding(
                kind="secret",
                detector="AWSKeyDetector",
                location=location,
                snippet=redacted_snippet(value),
                stable_hash=stable_hash(value),
            )
        )
    # GitHub token
    if re.search(r"ghp_[A-Za-z0-9]{36}", value):
        findings.append(
            RequestFinding(
                kind="secret",
                detector="GitHubTokenDetector",
                location=location,
                snippet=redacted_snippet(value),
                stable_hash=stable_hash(value),
            )
        )
    return findings


def _scan_value_for_pii(value: str, location: str) -> list[RequestFinding]:
    findings: list[RequestFinding] = []
    if _EMAIL_RE.search(value):
        findings.append(RequestFinding(kind="pii", detector="email", location=location, snippet=redacted_snippet(value), stable_hash=stable_hash(value)))
    if _SSN_RE.search(value):
        findings.append(RequestFinding(kind="pii", detector="ssn", location=location, snippet=redacted_snippet(value), stable_hash=stable_hash(value)))
    for m in _CC_RAW_RE.finditer(value):
        candidate = m.group()
        if _luhn_valid(candidate):
            findings.append(RequestFinding(kind="pii", detector="credit_card", location=location, snippet=redacted_snippet(value), stable_hash=stable_hash(value)))
            break
    # Phone: require at least 10 digits to reduce false positives
    for m in _PHONE_RE.finditer(value):
        digits = re.sub(r"\D", "", m.group())
        if len(digits) >= 10:
            findings.append(RequestFinding(kind="pii", detector="phone", location=location, snippet=redacted_snippet(value), stable_hash=stable_hash(value)))
            break
    return findings


def _scan_sensitive_value(value: str, location: str) -> list[RequestFinding]:
    findings: list[RequestFinding] = []
    findings.extend(_scan_value_for_secrets(value, location))
    findings.extend(_scan_value_for_pii(value, location))
    return findings


def _check_ip_for_ssrf(ip: str, hostname: str, config: SafeFetchConfig) -> None:
    try:
        parsed_ip = ipaddress.ip_address(ip)
    except ValueError as exc:
        raise SSRFBlockedError(f"DNS returned invalid address {ip!r} for {hostname!r}") from exc
    enforce_ip_policy(parsed_ip, hostname, config)


def validate_url_scheme(url: str) -> None:
    canonicalize_url(url, SafeFetchConfig.permissive_research())


def check_ssrf(url: str, config: SafeFetchConfig | None = None) -> None:
    """Resolve hostname and block if it points to a private address."""
    if config is None:
        config = SafeFetchConfig.agent_default()
    canonical = canonicalize_url(url, config)
    host = canonical.host

    # Direct IP literal in URL
    try:
        addr = ipaddress.ip_address(host)
        enforce_ip_policy(addr, host, config)
        return  # Public IP literal — no DNS needed
    except ValueError:
        pass  # Not an IP literal — resolve via DNS

    # DNS resolution
    try:
        results = socket.getaddrinfo(host, None)
    except socket.gaierror as exc:
        raise SSRFBlockedError(f"DNS resolution failed for {host!r}: {exc}") from exc

    for result in results:
        ip = result[4][0]
        _check_ip_for_ssrf(ip, host, config)


def scan_request(
    url: str,
    headers: dict[str, str],
    policy: Policy,
    config: SafeFetchConfig | None = None,
) -> list[RequestFinding]:
    """
    Scan URL query params and headers for secrets/PII.
    Returns findings; raises on STRICT if any found (except SSRF which always raises).
    """
    if config is None:
        config = SafeFetchConfig(request_policy=policy)

    findings: list[RequestFinding] = []

    try:
        parsed = urlparse(url)
    except ValueError:
        parsed = None

    if parsed is not None:
        if parsed.username:
            findings.extend(_scan_sensitive_value(unquote(parsed.username), "url:userinfo"))
        if parsed.password:
            findings.extend(_scan_sensitive_value(unquote(parsed.password), "url:userinfo"))

        for index, segment in enumerate(parsed.path.split("/")):
            if segment:
                findings.extend(_scan_sensitive_value(unquote(segment), f"path:{index}"))

        for param, value in parse_qsl(parsed.query, keep_blank_values=True):
            findings.extend(_scan_sensitive_value(unquote(param), f"query-key:{param}"))
            findings.extend(_scan_sensitive_value(unquote(value), f"query:{param}"))

    # Scan header values
    for header_name, header_value in headers.items():
        location = f"header:{header_name}"
        findings.extend(_scan_sensitive_value(header_value, location))

    # Apply policy
    if findings and policy == Policy.STRICT:
        secret_findings = [f for f in findings if f.kind == "secret"]
        pii_findings = [f for f in findings if f.kind == "pii"]
        if secret_findings:
            raise SecretLeakError(
                f"Secret detected in request ({secret_findings[0].detector} at {secret_findings[0].location})",
                finding=secret_findings[0],
            )
        if pii_findings:
            raise PIILeakError(
                f"PII detected in request ({pii_findings[0].detector} at {pii_findings[0].location})",
                finding=pii_findings[0],
            )
    elif findings and policy == Policy.WARN:
        for f in findings:
            log.warning("safe-fetch request finding: %s at %s", f.detector, f.location)

    # Canonical URL validation happens before any DNS or HTTP work.
    canonicalize_url(url, config)

    # SSRF check may perform DNS resolution, so it runs only after local leak
    # scanning has had a chance to block STRICT-policy secrets/PII pre-network.
    check_ssrf(url, config)

    return findings
