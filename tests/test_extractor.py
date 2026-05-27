"""Unit tests for extractor cascade."""
from __future__ import annotations

import pytest

from safe_fetch._exceptions import ExtractionFailedError
from safe_fetch._extractor import extract


_ARTICLE_HTML = """
<html>
<head><title>Test Article</title></head>
<body>
  <header><nav>Home | About | Contact</nav></header>
  <main>
    <article>
      <h1>How Async Python Works</h1>
      <p>Python's asyncio event loop allows you to write concurrent code using the async/await syntax.</p>
      <p>This makes it easy to handle many I/O-bound operations simultaneously without blocking the thread.</p>
    </article>
  </main>
  <footer>Copyright 2024</footer>
</body>
</html>
"""

_MINIMAL_HTML = """
<html><body><p>Short.</p></body></html>
"""


class TestExtractorCascade:
    def test_article_html_extracts_content(self):
        content, method = extract(_ARTICLE_HTML, url="https://example.com/article")
        assert len(content) > 20
        assert method in ("trafilatura", "readability+markdownify")

    def test_extraction_method_trafilatura_or_fallback(self):
        content, method = extract(_ARTICLE_HTML)
        assert method in ("trafilatura", "readability+markdownify")

    def test_minimal_html_fallback(self):
        # Trafilatura may return None for minimal content; fallback should handle it
        content, method = extract(_MINIMAL_HTML)
        assert content is not None
        assert len(content) > 0

    def test_x_status_initial_state_fallback(self):
        html = """
        <html><body><script>
        window.__INITIAL_STATE__={
          "entities":{
            "tweets":{"entities":{
              "2059119768662065523":{
                "full_text":"https://t.co/abc",
                "entities":{"urls":[{"url":"https://t.co/abc","expanded_url":"https://x.com/i/article/2059105486956380161"}]},
                "user":"1998221941300490241",
                "created_at":"2026-05-26T03:49:44.000Z",
                "favorite_count":215,
                "retweet_count":21,
                "reply_count":13,
                "quote_count":2,
                "bookmark_count":515
              }
            }},
            "users":{"entities":{
              "1998221941300490241":{"name":"Tony Simons","screen_name":"tonysimons_"}
            }}
          }
        };window.__META_DATA__={};
        </script></body></html>
        """

        content, method = extract(html, url="https://x.com/i/status/2059119768662065523")

        assert method == "x-initial-state"
        assert "# Tweet by Tony Simons (@tonysimons_)" in content
        assert "https://x.com/i/article/2059105486956380161" in content
        assert "Metrics: 215 likes, 21 reposts, 13 replies, 2 quotes, 515 bookmarks" in content

    def test_empty_html_raises_extraction_failed(self):
        with pytest.raises(ExtractionFailedError):
            extract("", url="https://example.com/empty", status_code=200)

    def test_extraction_failed_has_url_and_status(self):
        with pytest.raises(ExtractionFailedError) as exc_info:
            extract("", url="https://example.com/empty", status_code=404)
        assert exc_info.value.url == "https://example.com/empty"
        assert exc_info.value.status_code == 404

    def test_garbage_html_raises_or_extracts(self):
        # Should not raise unexpected exceptions — either extracts or raises ExtractionFailedError
        try:
            content, method = extract("<not real html at all!!!", url="https://example.com/")
            assert isinstance(content, str)
        except ExtractionFailedError:
            pass
