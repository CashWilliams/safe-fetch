"""safe-fetch: secure async web fetching for AI agents."""
from __future__ import annotations

import hashlib

from ._exceptions import (
    ClassifierError,
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
)
from ._types import (
    ContentIntegrity,
    FetchMetadata,
    InjectionFinding,
    RequestFinding,
    RiskAssessment,
    SafeFetchConfig,
    SafeFetchResult,
    SafetyEvent,
)

__all__ = [
    "safe_fetch",
    "SafeFetchConfig",
    "SafeFetchResult",
    "Policy",
    "SafeFetchError",
    "SecretLeakError",
    "PIILeakError",
    "SSRFBlockedError",
    "InvalidSchemeError",
    "InvalidURLError",
    "HostPolicyError",
    "InjectionDetectedError",
    "ExtractionFailedError",
    "FetchTimeoutError",
    "RedirectLimitError",
    "ResponseTooLargeError",
    "UnsupportedContentTypeError",
    "HTTPStatusError",
    "ClassifierError",
    "RequestFinding",
    "InjectionFinding",
    "FetchMetadata",
    "ContentIntegrity",
    "SafetyEvent",
    "RiskAssessment",
]


async def safe_fetch(
    url: str,
    config: SafeFetchConfig | None = None,
) -> SafeFetchResult:
    """
    Safely fetch web content for use in AI agents.

    Composes:
      1. Request guard — scheme validation, SSRF blocking, secret/PII scanning
      2. Fetch pipeline — content negotiation, .md probe, trafilatura, fallback
      3. Response guard — invisible char stripping, injection detection

    Args:
        url: The URL to fetch.
        config: Optional SafeFetchConfig; defaults are STRICT request policy,
                WARN response policy, 10s connect / 30s read timeouts.

    Returns:
        SafeFetchResult with clean markdown content and structured findings.

    Raises:
        InvalidSchemeError: URL scheme is not http/https.
        SSRFBlockedError: URL resolves to a private/reserved IP.
        SecretLeakError: Secret detected in URL/headers (STRICT policy).
        PIILeakError: PII detected in URL/headers (STRICT policy).
        FetchTimeoutError: Connect or read timeout.
        ExtractionFailedError: All content extraction methods failed.
        InjectionDetectedError: Injection detected in response (STRICT policy).
        RedirectLimitError: Redirect limit exceeded.
    """
    from datetime import datetime, timezone
    from time import monotonic

    from ._fetch_pipeline import fetch
    from ._marker import wrap_content
    from ._redaction import redact_url
    from ._request_guard import scan_request
    from ._response_guard import scan_response
    from ._safe_markdown import transform_safe_markdown
    from ._types import ContentIntegrity, FetchMetadata, RiskAssessment
    from ._url import canonicalize_url

    if config is None:
        config = SafeFetchConfig.agent_default()

    # Build the headers that will be sent (user_agent + extra_headers)
    outbound_headers = {
        "User-Agent": config.user_agent,
        **config.extra_headers,
    }

    # 1. Request guard
    started = monotonic()
    request_findings = scan_request(url, outbound_headers, config.request_policy, config)

    # 2. Fetch pipeline
    safety_events = []
    setattr(config, "_safety_events", safety_events)
    setattr(config, "_fetch_metadata", {})
    raw_content, final_url, extraction_method, status_code = await fetch(url, config)

    # 3. Response guard
    raw_content, response_findings = await scan_response(
        raw_content,
        config.response_policy,
        llm_client=config.llm_client,
        config=config,
        safety_events=safety_events,
    )

    if config.safe_markdown:
        safe_content, markdown_events = transform_safe_markdown(raw_content, config)
        safety_events.extend(markdown_events)
    else:
        safe_content = raw_content

    # 4. Content boundary wrapping
    fetched_at = datetime.now(timezone.utc)
    final_canonical_url = canonicalize_url(final_url, config).url
    wrapped_content, nonce = wrap_content(safe_content, redact_url(final_canonical_url), fetched_at)
    fetch_meta = getattr(config, "_fetch_metadata", {})
    elapsed_ms = (monotonic() - started) * 1000
    risk_reasons = []
    score = 0.0
    if request_findings:
        score += 0.3
        risk_reasons.append("request findings present")
    if response_findings:
        score += 0.5
        risk_reasons.append("response injection findings present")
    if safety_events:
        score += min(0.2, len(safety_events) * 0.05)
        risk_reasons.append("safety transformations or policy events recorded")
    if fetch_meta.get("redirect_chain"):
        score += 0.1
        risk_reasons.append("redirects followed")
    score = min(score, 1.0)
    risk_level = "high" if score >= 0.7 else "medium" if score >= 0.3 else "low"

    return SafeFetchResult(
        content=wrapped_content,
        raw_content=raw_content,
        safe_content=safe_content,
        content_marker=nonce,
        url=final_canonical_url,
        status_code=status_code,
        extraction_method=extraction_method,
        request_findings=request_findings,
        response_findings=response_findings,
        metadata=FetchMetadata(
            final_url=final_canonical_url,
            redacted_source_url=redact_url(final_canonical_url),
            source_host=canonicalize_url(final_canonical_url, config).host,
            status_code=status_code,
            content_type=fetch_meta.get("content_type", ""),
            content_length=fetch_meta.get("content_length"),
            etag=fetch_meta.get("etag"),
            last_modified=fetch_meta.get("last_modified"),
            redirect_chain=fetch_meta.get("redirect_chain", []),
            fetched_at=fetched_at.strftime("%Y-%m-%dT%H:%M:%SZ"),
            elapsed_ms=elapsed_ms,
        ),
        integrity=ContentIntegrity(
            raw_content_sha256=hashlib.sha256(raw_content.encode()).hexdigest(),
            safe_content_sha256=hashlib.sha256(safe_content.encode()).hexdigest(),
        ),
        safety_events=safety_events,
        risk=RiskAssessment(score=score, level=risk_level, reasons=risk_reasons),
    )
