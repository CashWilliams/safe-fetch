## Why

The `llms.txt` probe in the current fetch pipeline returns a site-level index, not the content of the requested URL — making it useless for page-specific fetches and a source of misleading results. A parallel `.md` URL probe gives a zero-latency-penalty path to clean markdown for the many platforms (GitHub, documentation sites, wikis) that serve `.md` files alongside their HTML pages.

## What Changes

- **Remove** `llms.txt` discovery from the per-URL fetch path; it is not a substitute for page content and causes incorrect results when a page-specific fetch is requested
- **Add** a parallel `.md` URL probe: when fetching any URL, simultaneously request the same URL with `.md` appended; if the probe returns HTTP 200 with `text/markdown` or `text/plain`, use that content and skip HTML extraction
- The probe runs concurrently with the primary fetch via `asyncio.gather` — no added latency when `.md` does not exist
- `Accept` header content negotiation already in place is unchanged

## Capabilities

### New Capabilities

### Modified Capabilities
- `fetch-pipeline`: `llms.txt discovery` requirement is removed; new `.md probe` requirement replaces it in the cascade order; `extraction_method` gains a new value `"md-probe"`

## Impact

- `safe_fetch/_fetch_pipeline.py`: remove `_try_llms_txt`, add `_try_md_probe` using `asyncio.gather`
- `pyproject.toml`: `llms-txt` dependency can be removed
- `openspec/specs/fetch-pipeline/spec.md`: `llms.txt discovery` requirement removed, `.md probe` requirement added
- Tests: remove llms.txt tests, add `.md` probe tests covering parallel fetch, 200/404 cases, and correct `extraction_method`
