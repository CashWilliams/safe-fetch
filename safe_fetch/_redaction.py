"""Redaction helpers for findings, messages, and metadata."""
from __future__ import annotations

import hashlib
import re
from urllib.parse import parse_qsl, quote, urlencode, urlparse, urlunparse


def stable_hash(value: str) -> str:
    """Return a stable SHA-256 hash for a sensitive value."""
    return hashlib.sha256(value.encode("utf-8", errors="replace")).hexdigest()


def redact_value(value: str) -> str:
    """Return a non-reversible placeholder for a sensitive value."""
    if not value:
        return "[REDACTED]"
    return f"[REDACTED:{stable_hash(value)[:12]}]"


def redacted_snippet(value: str, limit: int = 100) -> str:
    """Return a bounded snippet that never contains the original value."""
    return redact_value(value)[:limit]


_SENSITIVE_PATH_RE = re.compile(
    r"([A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}|AKIA[0-9A-Z]{16}|ghp_[A-Za-z0-9]{36}|token|secret|api[_-]?key)",
    re.IGNORECASE,
)


def redact_url(url: str) -> str:
    """Redact credentials, query values, and sensitive-looking path segments."""
    parsed = urlparse(url)
    host = parsed.hostname or ""
    if ":" in host and not host.startswith("["):
        host = f"[{host}]"
    netloc = host
    if parsed.port is not None:
        netloc = f"{netloc}:{parsed.port}"

    path_segments = []
    for segment in parsed.path.split("/"):
        if _SENSITIVE_PATH_RE.search(segment):
            path_segments.append(quote(redact_value(segment), safe=""))
        else:
            path_segments.append(segment)
    path = "/".join(path_segments)

    query = urlencode(
        [(key, redact_value(value) if value else value) for key, value in parse_qsl(parsed.query, keep_blank_values=True)],
        doseq=True,
    )
    return urlunparse((parsed.scheme, netloc, path, "", query, ""))
