"""Compatibility tests for public API imports and result fields."""
from __future__ import annotations

from dataclasses import asdict

from safe_fetch import (
    ClassifierError,
    ContentIntegrity,
    FetchMetadata,
    HTTPStatusError,
    HostPolicyError,
    InvalidURLError,
    Policy,
    ResponseTooLargeError,
    RiskAssessment,
    SafeFetchConfig,
    SafeFetchError,
    SafeFetchResult,
    SafetyEvent,
    UnsupportedContentTypeError,
)


def test_new_exceptions_are_public_and_catchable_as_safe_fetch_error():
    exception_types = (
        InvalidURLError,
        HostPolicyError,
        ResponseTooLargeError,
        UnsupportedContentTypeError,
        HTTPStatusError,
        ClassifierError,
    )

    for exception_type in exception_types:
        assert issubclass(exception_type, SafeFetchError)


def test_metadata_dataclasses_are_public_and_json_serializable():
    metadata = FetchMetadata(final_url="https://example.com/", status_code=200)
    integrity = ContentIntegrity(raw_content_sha256="raw", safe_content_sha256="safe")
    event = SafetyEvent(category="markdown", action="neutralized", count=1)
    risk = RiskAssessment(score=0.2, level="low", reasons=["clean source"])

    assert asdict(metadata)["final_url"] == "https://example.com/"
    assert asdict(integrity)["safe_content_sha256"] == "safe"
    assert asdict(event)["category"] == "markdown"
    assert asdict(risk)["reasons"] == ["clean source"]


def test_config_presets_and_new_defaults_are_available():
    default = SafeFetchConfig.agent_default()
    strict = SafeFetchConfig.strict_enterprise()
    permissive = SafeFetchConfig.permissive_research()

    assert default.request_policy == Policy.STRICT
    assert default.response_policy == Policy.WARN
    assert default.total_timeout == 60.0
    assert default.max_response_bytes == 10_000_000
    assert default.max_redirects == 5
    assert default.max_extraction_workers == 4
    assert default.safe_markdown is True
    assert "text/html" in default.allowed_content_types

    assert strict.allow_http is False
    assert strict.response_policy == Policy.STRICT
    assert strict.classifier_failure_policy == Policy.STRICT

    assert permissive.request_policy == Policy.PERMISSIVE
    assert permissive.http_status_policy == "all"
    assert permissive.safe_markdown is False


def test_existing_result_constructor_and_new_fields_are_compatible():
    result = SafeFetchResult(
        content="<web_content>body</web_content>",
        raw_content="body",
        content_marker="abc123",
        url="https://example.com/",
        status_code=200,
        extraction_method="content-negotiation",
    )

    assert result.raw_content == "body"
    assert result.safe_content == ""
    assert result.request_findings == []
    assert result.response_findings == []
    assert isinstance(result.metadata, FetchMetadata)
    assert isinstance(result.integrity, ContentIntegrity)
    assert result.safety_events == []
    assert isinstance(result.risk, RiskAssessment)
