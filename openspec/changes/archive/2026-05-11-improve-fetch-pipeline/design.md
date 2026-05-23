## Context

The fetch pipeline currently tries content discovery in this order: Accept-header negotiation → llms.txt → trafilatura → readability+markdownify. The `llms.txt` step is broken for page-specific fetches — it returns a site-level index document regardless of which page was requested. Many platforms (GitHub, Read the Docs, MkDocs, most wikis) serve raw markdown files at predictable `.md` URLs. Probing for these is a clean, zero-dependency improvement to content quality.

## Goals / Non-Goals

**Goals:**
- Run a `.md` URL probe in parallel with the primary fetch so there is no latency penalty on miss
- Use `.md` content when available, maintaining `extraction_method="md-probe"` for observability
- Remove `llms.txt` discovery and its dependency entirely
- Keep the change contained to `_fetch_pipeline.py` and `pyproject.toml`

**Non-Goals:**
- Probing other alternate URL patterns (`.txt`, `/raw/`, `/plain`) — one probe keeps it simple
- Caching `.md` probe results across calls
- Making the `.md` probe opt-in/opt-out via config — it's always on; the latency cost on miss is near-zero
- Re-introducing `llms.txt` in any form

## Decisions

### 1. Parallel fetch with `asyncio.gather`

**Decision:** Fire the primary URL fetch and the `.md` probe simultaneously using `asyncio.gather`. If the probe returns 200 with a text content-type, use it and discard the primary response. If not, use the primary response as normal.

**Rationale:** The probe adds zero wall-clock latency on the happy path where both complete around the same time. Sequential probe-then-fetch would add a full round trip on miss. `asyncio.gather` with `return_exceptions=True` lets us handle probe failure gracefully without cancelling the primary fetch.

**Alternatives considered:** Probe first, only fetch primary on miss — simpler but doubles latency on miss (the common case for most non-docs URLs). Background task with timeout — more complex cancellation logic for no benefit.

### 2. `.md` URL construction: simple suffix append

**Decision:** Append `.md` to the full path component of the URL. `https://example.com/docs/page` → `https://example.com/docs/page.md`. If the URL already ends in `.md`, skip the probe.

**Rationale:** This matches how GitHub, MkDocs, Sphinx, and most documentation platforms organize raw markdown. More complex path rewriting (e.g., inserting `/raw/`) is platform-specific and not generalizable.

**Edge cases handled:**
- URL already ends in `.md` → skip probe (avoid double-fetch)
- URL has query string → append `.md` to path only, preserve query string
- Probe URL must pass SSRF and scheme checks (same host, so this is guaranteed if primary passed)

### 3. Acceptance criteria for probe response

**Decision:** Accept the probe result if: HTTP status is 200, and `Content-Type` contains `text/markdown` or `text/plain`. Reject silently on any other status, content-type, or exception.

**Rationale:** A 200 with HTML at `.md` (some servers serve their 404 page with 200) should be rejected to avoid garbage content. Checking content-type filters these out. Any network error on the probe should be swallowed — the primary fetch is the fallback.

### 4. Remove `llms-txt` dependency

**Decision:** Remove `llms-txt` from `pyproject.toml` dependencies along with `_try_llms_txt`.

**Rationale:** No remaining code uses it. Fewer dependencies = smaller install, fewer supply chain risks.

## Risks / Trade-offs

- **Double network requests per fetch** → Both the primary URL and `.md` probe fire simultaneously. On a cold connection this is two TCP handshakes in parallel, not two sequential ones — acceptable overhead. The probe uses the same `httpx.AsyncClient` instance and connection pool.
- **`.md` URL exists but serves wrong content** → A server could return 200 + text/plain for `.md` with content unrelated to the original page. Mitigated by content-type check; can't fully prevent without content validation.
- **Removing `llms.txt` may surprise callers checking `extraction_method`** → `"llms-txt"` will no longer appear as a value. This is a behaviour change but not a breaking API change — `extraction_method` is informational. Document in release notes.
