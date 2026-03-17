from app.services.protest_feeds import (
    get_protest_feed_urls_from_db,
    normalize_feed_url,
    save_protest_feed_urls,
    validate_protest_feed_urls,
)


def test_normalize_feed_url_accepts_http_https():
    assert normalize_feed_url("https://Example.com/feed.xml") == "https://example.com/feed.xml"
    assert normalize_feed_url("http://example.com/rss") == "http://example.com/rss"


def test_normalize_feed_url_rejects_invalid():
    assert normalize_feed_url("ftp://example.com/feed.xml") == ""
    assert normalize_feed_url("notaurl") == ""
    assert normalize_feed_url("") == ""


def test_validate_protest_feed_urls_requires_at_least_one_valid():
    cleaned, errors = validate_protest_feed_urls(["", " ", "notaurl"])
    assert cleaned == []
    assert errors


def test_validate_protest_feed_urls_detects_duplicates():
    cleaned, errors = validate_protest_feed_urls(
        [
            "https://example.com/feed.xml",
            "https://example.com/feed.xml",
        ]
    )
    assert cleaned == ["https://example.com/feed.xml"]
    assert any("duplicada" in item.lower() for item in errors)


def test_save_and_get_protest_feed_urls(app):
    with app.app_context():
        save_protest_feed_urls(
            [
                "https://example.com/feed-a.xml",
                "https://example.com/feed-b.xml",
            ]
        )
        rows = get_protest_feed_urls_from_db()
        assert rows == [
            "https://example.com/feed-a.xml",
            "https://example.com/feed-b.xml",
        ]
