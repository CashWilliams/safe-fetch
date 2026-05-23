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
    stable_hash: str | None = None


@dataclass
class InjectionFinding:
    """An injection finding from the response scan."""

    confidence: str  # "HIGH", "MEDIUM", "LOW"
    pattern_matched: str | None  # regex pattern that matched, or None
    heuristic: str | None  # heuristic name, or None
    snippet: str  # up to 100 chars of surrounding context


@dataclass
class FetchMetadata:
    """Provenance metadata for a fetch."""

    final_url: str = ""
    redacted_source_url: str = ""
    source_host: str = ""
    status_code: int = 0
    content_type: str = ""
    content_length: int | None = None
    etag: str | None = None
    last_modified: str | None = None
    redirect_chain: list[dict[str, str]] = field(default_factory=list)
    fetched_at: str = ""
    elapsed_ms: float = 0.0


@dataclass
class ContentIntegrity:
    """Content hashes for raw and safe output."""

    raw_content_sha256: str = ""
    safe_content_sha256: str = ""


@dataclass
class SafetyEvent:
    """Structured safety event emitted by guards and transforms."""

    category: str
    action: str
    message: str = ""
    count: int | None = None
    severity: str = "info"
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class RiskAssessment:
    """Aggregate advisory risk score."""

    score: float = 0.0
    level: str = "low"
    reasons: list[str] = field(default_factory=list)


@dataclass
class SafeFetchConfig:
    """Configuration for safe_fetch()."""

    request_policy: Policy = Policy.STRICT
    response_policy: Policy = Policy.WARN
    connect_timeout: float = 10.0
    read_timeout: float = 30.0
    total_timeout: float | None = 60.0
    max_response_bytes: int = 10_000_000
    max_redirects: int = 5
    max_extraction_workers: int = 4
    llm_client: Any = None
    classifier_timeout: float = 5.0
    classifier_failure_policy: Policy = Policy.WARN
    user_agent: str = "safe-fetch/1.0 (LLM-agent)"
    extra_headers: dict = field(default_factory=dict)
    allow_http: bool = True
    allowed_hosts: set[str] = field(default_factory=set)
    allowed_host_suffixes: set[str] = field(default_factory=set)
    blocked_hosts: set[str] = field(default_factory=set)
    blocked_cidrs: set[str] = field(default_factory=set)
    allowed_cidrs: set[str] = field(default_factory=set)
    allowed_content_types: set[str] = field(
        default_factory=lambda: {
            "text/html",
            "text/plain",
            "text/markdown",
            "application/xhtml+xml",
        }
    )
    http_status_policy: str = "2xx"
    redaction_mode: str = "snippet"
    safe_markdown: bool = True
    rendered_text_mode: bool = False

    @classmethod
    def agent_default(cls) -> "SafeFetchConfig":
        """Return the default policy for agent/RAG fetching."""
        return cls()

    @classmethod
    def strict_enterprise(cls) -> "SafeFetchConfig":
        """Return a fail-closed configuration for high-risk deployments."""
        return cls(
            request_policy=Policy.STRICT,
            response_policy=Policy.STRICT,
            allow_http=False,
            classifier_failure_policy=Policy.STRICT,
            http_status_policy="2xx",
            safe_markdown=True,
        )

    @classmethod
    def permissive_research(cls) -> "SafeFetchConfig":
        """Return a compatibility-oriented configuration for analysis workflows."""
        return cls(
            request_policy=Policy.PERMISSIVE,
            response_policy=Policy.WARN,
            allow_http=True,
            classifier_failure_policy=Policy.WARN,
            http_status_policy="all",
            safe_markdown=False,
        )


@dataclass
class SafeFetchResult:
    """Result returned by safe_fetch()."""

    content: str
    raw_content: str
    content_marker: str
    url: str
    status_code: int
    extraction_method: str
    safe_content: str = ""
    request_findings: list[RequestFinding] = field(default_factory=list)
    response_findings: list[InjectionFinding] = field(default_factory=list)
    metadata: FetchMetadata = field(default_factory=FetchMetadata)
    integrity: ContentIntegrity = field(default_factory=ContentIntegrity)
    safety_events: list[SafetyEvent] = field(default_factory=list)
    risk: RiskAssessment = field(default_factory=RiskAssessment)
