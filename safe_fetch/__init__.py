"""safe-fetch: secure async web fetching for AI agents."""
from __future__ import annotations

from ._exceptions import (
    ExtractionFailedError,
    FetchTimeoutError,
    InjectionDetectedError,
    InvalidSchemeError,
    PIILeakError,
    Policy,
    RedirectLimitError,
    SSRFBlockedError,
    SafeFetchError,
    SecretLeakError,
)
from ._types import (
    InjectionFinding,
    RequestFinding,
    SafeFetchConfig,
    SafeFetchResult,
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
    "InjectionDetectedError",
    "ExtractionFailedError",
    "FetchTimeoutError",
    "RedirectLimitError",
    "RequestFinding",
    "InjectionFinding",
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

    from ._fetch_pipeline import fetch
    from ._marker import wrap_content
    from ._request_guard import scan_request
    from ._response_guard import scan_response

    if config is None:
        config = SafeFetchConfig()

    # Build the headers that will be sent (user_agent + extra_headers)
    outbound_headers = {
        "User-Agent": config.user_agent,
        **config.extra_headers,
    }

    # 1. Request guard
    request_findings = scan_request(url, outbound_headers, config.request_policy)

    # 2. Fetch pipeline
    raw_content, final_url, extraction_method, status_code = await fetch(url, config)

    # 3. Response guard
    clean_content, response_findings = await scan_response(
        raw_content,
        config.response_policy,
        llm_client=config.llm_client,
    )

    # 4. Content boundary wrapping
    fetched_at = datetime.now(timezone.utc)
    wrapped_content, nonce = wrap_content(clean_content, final_url, fetched_at)

    return SafeFetchResult(
        content=wrapped_content,
        raw_content=clean_content,
        content_marker=nonce,
        url=final_url,
        status_code=status_code,
        extraction_method=extraction_method,
        request_findings=request_findings,
        response_findings=response_findings,
    )
