## 1. Data Model

- [x] 1.1 Add `raw_content: str` field to `SafeFetchResult` in `safe_fetch/_types.py`
- [x] 1.2 Add `content_marker: str` field to `SafeFetchResult` in `safe_fetch/_types.py`

## 2. Wrapping Logic

- [x] 2.1 Create `safe_fetch/_marker.py` with `generate_nonce() -> str` using `secrets.token_hex(16)`
- [x] 2.2 Implement `wrap_content(content: str, url: str, fetched_at: datetime) -> tuple[str, str]` in `_marker.py`: returns `(wrapped, nonce)`, HTML-escaping `source` and `fetched_at` attributes
- [x] 2.3 Add `fetched_at` timestamp capture (UTC `datetime.now(UTC)`) in `safe_fetch()` just before the wrapping step

## 3. Pipeline Integration

- [x] 3.1 Call `wrap_content(clean_content, final_url, fetched_at)` in `safe_fetch/__init__.py` after `scan_response()` returns
- [x] 3.2 Populate `SafeFetchResult` with `content=wrapped`, `raw_content=clean_content`, `content_marker=nonce`

## 4. Tests

- [x] 4.1 Unit-test `generate_nonce()`: assert 32-char hex string, assert two calls return different values
- [x] 4.2 Unit-test `wrap_content()`: assert opening tag contains `untrusted="true"`, correct `source`, `fetched_at`, `marker`; assert closing tag has same `marker`; assert body equals input content
- [x] 4.3 Unit-test URL special-character escaping: `&` → `&amp;`, `"` → `&quot;`
- [x] 4.4 Integration-test via `safe_fetch()` mock: assert `result.content` starts with `<web_content`, `result.raw_content` is unwrapped, `result.content_marker` matches nonces in both tags
- [x] 4.5 Assert nonce uniqueness across two `safe_fetch()` calls in the same test
- [x] 4.6 Update any existing tests that assert on the exact value of `result.content` to use `result.raw_content` instead
