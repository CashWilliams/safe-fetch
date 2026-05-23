"""Public-facing dataclasses for safe-fetch."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ._exceptions import Policy


@dataclass
class RequestFinding:
    """A secret or PII finding from the pre-request scan."""

    kind: str  # "secret" or "pii"
    detector: str  # e.g. "AWSKeyDetector", "email", "credit_card"
    location: str  # e.g. "query:api_key" or "header:Authorization"
    snippet: str  # up to 100 chars of surrounding context (redacted)


@dataclass
class InjectionFinding:
    """An injection finding from the response scan."""

    confidence: str  # "HIGH", "MEDIUM", "LOW"
    pattern_matched: str | None  # regex pattern that matched, or None
    heuristic: str | None  # heuristic name, or None
    snippet: str  # up to 100 chars of surrounding context


@dataclass
class SafeFetchConfig:
    """Configuration for safe_fetch()."""

    request_policy: Policy = Policy.STRICT
    response_policy: Policy = Policy.WARN
    connect_timeout: float = 10.0
    read_timeout: float = 30.0
    llm_client: Any = None
    user_agent: str = "safe-fetch/1.0 (LLM-agent)"
    extra_headers: dict = field(default_factory=dict)


@dataclass
class SafeFetchResult:
    """Result returned by safe_fetch()."""

    content: str
    raw_content: str
    content_marker: str
    url: str
    status_code: int
    extraction_method: str
    request_findings: list[RequestFinding] = field(default_factory=list)
    response_findings: list[InjectionFinding] = field(default_factory=list)
