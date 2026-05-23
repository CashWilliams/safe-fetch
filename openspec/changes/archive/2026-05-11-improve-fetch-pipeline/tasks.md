## 1. Remove llms.txt

- [x] 1.1 Delete `_try_llms_txt()` function from `safe_fetch/_fetch_pipeline.py`
- [x] 1.2 Remove the `llms_txt` import and the `_try_llms_txt` call from the `fetch()` function body
- [x] 1.3 Remove `llms-txt>=0.0.6` from `dependencies` in `pyproject.toml`

## 2. Add .md Probe

- [x] 2.1 Implement `_build_md_url(url: str) -> str | None` in `_fetch_pipeline.py`: appends `.md` to the URL path; returns `None` if the URL already ends in `.md`
- [x] 2.2 Implement `_try_md_probe(md_url: str, client: httpx.AsyncClient) -> str | None`: GETs `md_url`, returns response text if status 200 and content-type is `text/markdown` or `text/plain`, otherwise returns `None`; swallows all exceptions
- [x] 2.3 In `fetch()`, after receiving an HTML response, call `asyncio.gather(primary_html_task, _try_md_probe(...))` — restructure the primary fetch loop so the HTML body and the probe run concurrently
- [x] 2.4 If probe returns non-None, return `(probe_content, final_url, "md-probe", status_code)` and skip HTML extraction

## 3. Tests

- [x] 3.1 Remove `test_llms_txt_used_when_available` from `tests/test_fetch_pipeline.py`
- [x] 3.2 Remove `test_llms_txt_extraction` from `tests/test_integration.py`
- [x] 3.3 Test `.md` probe success: mock primary returns HTML, mock `.md` URL returns 200 + `text/markdown`; assert `extraction_method="md-probe"` and content matches probe response
- [x] 3.4 Test `.md` probe 404: mock `.md` URL returns 404; assert pipeline falls through to trafilatura/readability
- [x] 3.5 Test `.md` probe wrong content-type: mock `.md` URL returns 200 + `text/html`; assert probe is discarded and HTML extraction runs
- [x] 3.6 Test `.md` probe exception: mock `.md` request raises `httpx.ConnectError`; assert no error raised and HTML extraction runs
- [x] 3.7 Test URL already ending in `.md`: assert no second request is made (probe skipped)
- [x] 3.8 Test `.md` probe does not fire when primary response is already `text/markdown` (content negotiation path)
