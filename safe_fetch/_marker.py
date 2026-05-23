"""Content boundary marker generation for safe-fetch."""
from __future__ import annotations

import secrets
from datetime import datetime, timezone
from html import escape


def generate_nonce() -> str:
    """Return a cryptographically random 32-character hex nonce."""
    return secrets.token_hex(16)


def wrap_content(content: str, url: str, fetched_at: datetime) -> tuple[str, str]:
    """Wrap content in XML-style boundary tags with a fresh nonce.

    Returns:
        (wrapped_content, nonce) where nonce is also embedded in both tags.
    """
    nonce = generate_nonce()
    escaped_url = escape(url, quote=True)
    escaped_ts = escape(fetched_at.strftime("%Y-%m-%dT%H:%M:%SZ"), quote=True)

    wrapped = (
        f'<web_content untrusted="true" source="{escaped_url}"'
        f' fetched_at="{escaped_ts}" marker="{nonce}">\n'
        f"{content}\n"
        f'</web_content marker="{nonce}">'
    )
    return wrapped, nonce
