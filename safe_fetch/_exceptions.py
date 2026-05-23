"""Exception hierarchy for safe-fetch."""
from __future__ import annotations

from enum import Enum


class Policy(Enum):
    STRICT = "strict"
    WARN = "warn"
    PERMISSIVE = "permissive"


class SafeFetchError(Exception):
    """Base exception for all safe-fetch errors."""


class SecretLeakError(SafeFetchError):
    """Secret detected in request URL or headers."""

    def __init__(self, message: str, finding=None) -> None:
        super().__init__(message)
        self.finding = finding


class PIILeakError(SafeFetchError):
    """PII detected in request URL or headers."""

    def __init__(self, message: str, finding=None) -> None:
        super().__init__(message)
        self.finding = finding


class SSRFBlockedError(SafeFetchError):
    """SSRF / private IP blocked. Always raised regardless of policy."""


class InvalidSchemeError(SafeFetchError):
    """Disallowed URL scheme."""


class InjectionDetectedError(SafeFetchError):
    """Injection detected in response under STRICT policy."""

    def __init__(self, message: str, findings=None) -> None:
        super().__init__(message)
        self.findings = findings or []


class ExtractionFailedError(SafeFetchError):
    """All extraction methods failed."""

    def __init__(self, message: str, url: str = "", status_code: int = 0) -> None:
        super().__init__(message)
        self.url = url
        self.status_code = status_code


class FetchTimeoutError(SafeFetchError):
    """Connect or read timeout."""

    def __init__(self, message: str, phase: str = "") -> None:
        super().__init__(message)
        self.phase = phase


class RedirectLimitError(SafeFetchError):
    """HTTP redirect limit exceeded."""

    def __init__(self, message: str, redirects: int = 0) -> None:
        super().__init__(message)
        self.redirects = redirects
