"""Canonical URL validation and host policy helpers."""
from __future__ import annotations

import ipaddress
import re
import unicodedata
from dataclasses import dataclass
from urllib.parse import urlparse, urlunparse

from ._exceptions import HostPolicyError, InvalidSchemeError, InvalidURLError, SSRFBlockedError
from ._types import SafeFetchConfig

_ALLOWED_SCHEMES = {"http", "https"}
_CONTROL_RE = re.compile(r"[\x00-\x1f\x7f]")
_DANGEROUS_NFKC_CHARS = set("/?#@:")


@dataclass(frozen=True)
class CanonicalURL:
    """Security-validated URL target."""

    raw: str
    url: str
    scheme: str
    host: str
    port: int | None
    path: str
    query: str
    is_ip_literal: bool


def _normalize_host(host: str) -> str:
    host = host.rstrip(".").lower()
    nfkc = unicodedata.normalize("NFKC", host)
    if nfkc != host and any(char in _DANGEROUS_NFKC_CHARS for char in nfkc):
        raise InvalidURLError("Hostname contains unsafe Unicode normalization")
    try:
        ascii_host = nfkc.encode("idna").decode("ascii").lower()
    except UnicodeError as exc:
        raise InvalidURLError("Hostname is not valid IDNA") from exc
    if not ascii_host:
        raise InvalidURLError("URL host is empty")
    return ascii_host


def _is_local_name(host: str) -> bool:
    return host == "localhost" or host.endswith(".localhost") or host.endswith(".local")


def _looks_ambiguous_ipv4(host: str) -> bool:
    lower = host.lower()
    if lower.isdigit() or "0x" in lower:
        return True
    labels = lower.split(".")
    if len(labels) == 4 and all(label.isdigit() for label in labels):
        return any(len(label) > 1 and label.startswith("0") for label in labels)
    return False


def _parse_ip_literal(host: str) -> ipaddress.IPv4Address | ipaddress.IPv6Address | None:
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        return None
    if getattr(ip, "ipv4_mapped", None) is not None:
        raise InvalidURLError("IPv4-mapped IPv6 addresses are not allowed")
    return ip


def _cidr_networks(values: set[str], field_name: str) -> list[ipaddress._BaseNetwork]:
    networks = []
    for value in values:
        try:
            networks.append(ipaddress.ip_network(value, strict=False))
        except ValueError as exc:
            raise HostPolicyError(f"Invalid CIDR in {field_name}: {value!r}") from exc
    return networks


def _host_matches_suffix(host: str, suffix: str) -> bool:
    normalized = suffix.lower()
    if not normalized.startswith("."):
        normalized = "." + normalized
    return host.endswith(normalized)


def enforce_host_policy(host: str, config: SafeFetchConfig) -> None:
    """Apply hostname allow/block policy without performing DNS."""
    blocked_hosts = {value.rstrip(".").lower() for value in config.blocked_hosts}
    allowed_hosts = {value.rstrip(".").lower() for value in config.allowed_hosts}
    allowed_suffixes = {value.lower() for value in config.allowed_host_suffixes}

    if host in blocked_hosts:
        raise HostPolicyError(f"Host {host!r} is blocked")
    if allowed_hosts or allowed_suffixes:
        exact_allowed = host in allowed_hosts
        suffix_allowed = any(_host_matches_suffix(host, suffix) for suffix in allowed_suffixes)
        if not exact_allowed and not suffix_allowed:
            raise HostPolicyError(f"Host {host!r} is not in the allowed host policy")


def enforce_ip_policy(
    ip: ipaddress.IPv4Address | ipaddress.IPv6Address,
    host: str,
    config: SafeFetchConfig,
) -> None:
    """Apply CIDR policy and globally-routable default for a resolved address."""
    blocked = _cidr_networks(config.blocked_cidrs, "blocked_cidrs")
    allowed = _cidr_networks(config.allowed_cidrs, "allowed_cidrs")

    if any(ip in network for network in blocked):
        raise HostPolicyError(f"IP {str(ip)!r} for host {host!r} is blocked by CIDR policy")
    if allowed:
        if any(ip in network for network in allowed):
            return
        raise HostPolicyError(f"IP {str(ip)!r} for host {host!r} is not in allowed CIDRs")
    if not ip.is_global:
        raise SSRFBlockedError(f"SSRF blocked: {host!r} resolved to non-global IP {str(ip)!r}")


def canonicalize_url(raw_url: str, config: SafeFetchConfig | None = None) -> CanonicalURL:
    """Return a canonical URL object or raise for unsafe targets."""
    if config is None:
        config = SafeFetchConfig.agent_default()

    if _CONTROL_RE.search(raw_url):
        raise InvalidURLError("URL contains ASCII control characters")
    if "\\" in raw_url:
        raise InvalidURLError("URL contains backslashes")

    try:
        parsed = urlparse(raw_url)
    except ValueError as exc:
        raise InvalidURLError("URL is malformed") from exc
    if parsed.scheme not in _ALLOWED_SCHEMES:
        raise InvalidSchemeError(
            f"Scheme {parsed.scheme!r} is not allowed; only http/https are permitted"
        )
    if parsed.scheme == "http" and not config.allow_http:
        raise InvalidURLError("HTTP URLs are not allowed by policy")
    if not parsed.netloc:
        raise InvalidURLError("URL netloc is empty")
    if parsed.fragment:
        raise InvalidURLError("URL fragments are not allowed")
    if parsed.username is not None or parsed.password is not None:
        raise InvalidURLError("URL userinfo is not allowed")

    try:
        port = parsed.port
    except ValueError as exc:
        raise InvalidURLError("URL port is invalid") from exc

    try:
        raw_host = parsed.hostname
    except ValueError as exc:
        raise InvalidURLError("Malformed IPv6 brackets") from exc
    if not raw_host:
        raise InvalidURLError("URL host is empty")
    if raw_url.count("[") != raw_url.count("]"):
        raise InvalidURLError("Malformed IPv6 brackets")

    host = _normalize_host(raw_host)
    if "%" in host:
        raise InvalidURLError("Percent-encoded hosts are not allowed")
    if _looks_ambiguous_ipv4(host):
        raise InvalidURLError("Ambiguous IPv4 host encodings are not allowed")
    if _is_local_name(host):
        raise SSRFBlockedError(f"SSRF blocked: local-name host {host!r} is not allowed")

    enforce_host_policy(host, config)
    ip = _parse_ip_literal(host)
    if ip is not None:
        enforce_ip_policy(ip, host, config)

    path = parsed.path or "/"
    netloc_host = f"[{host}]" if ":" in host else host
    canonical = urlunparse((parsed.scheme.lower(), netloc_host if port is None else f"{netloc_host}:{port}", path, "", parsed.query, ""))
    return CanonicalURL(
        raw=raw_url,
        url=canonical,
        scheme=parsed.scheme.lower(),
        host=host,
        port=port,
        path=path,
        query=parsed.query,
        is_ip_literal=ip is not None,
    )
