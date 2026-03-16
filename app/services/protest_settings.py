"""
Protest configuration stored in DB (site_settings table).
All keys use the prefix "protest.".
Values fall back to hardcoded defaults so the app starts with no configuration at all.
"""

from app.services.settings import get_setting, set_setting

# --- key constants ---
KEY_RSS_FEEDS = "protest.rss_feeds"
KEY_FETCH_TIMEOUT = "protest.fetch_timeout_seconds"
KEY_FRONTEND_REFRESH = "protest.frontend_refresh_seconds"
KEY_MIN_CONFIDENCE = "protest.min_confidence_to_show"
KEY_REQUIRE_SOURCE_URL = "protest.require_source_url"
KEY_ALLOW_UNRESOLVED = "protest.allow_unresolved_to_map"
KEY_MAX_ITEMS_PER_FEED = "protest.max_items_per_feed"
KEY_MAX_POST_AGE_DAYS = "protest.max_post_age_days"
KEY_KEYWORDS_STRONG = "protest.keywords_strong"
KEY_KEYWORDS_CONTEXT = "protest.keywords_context"
KEY_KEYWORDS_WEAK = "protest.keywords_weak"
KEY_PLACE_ALIASES_JSON = "protest.place_aliases_json"
KEY_SOURCE_NAME_OVERRIDES_JSON = "protest.source_name_overrides_json"

# Defaults (identical to the previous env-var defaults)
_DEFAULTS = {
    KEY_RSS_FEEDS: "",
    KEY_FETCH_TIMEOUT: "30",
    KEY_FRONTEND_REFRESH: "300",
    KEY_MIN_CONFIDENCE: "35",
    KEY_REQUIRE_SOURCE_URL: "1",
    KEY_ALLOW_UNRESOLVED: "0",
    KEY_MAX_ITEMS_PER_FEED: "120",
    KEY_MAX_POST_AGE_DAYS: "30",
    KEY_KEYWORDS_STRONG: "",
    KEY_KEYWORDS_CONTEXT: "",
    KEY_KEYWORDS_WEAK: "",
    KEY_PLACE_ALIASES_JSON: "",
    KEY_SOURCE_NAME_OVERRIDES_JSON: "",
}


def _get(key):
    return get_setting(key, _DEFAULTS[key])


def get_rss_feeds_raw() -> str:
    return _get(KEY_RSS_FEEDS)


def get_fetch_timeout_seconds_raw() -> str:
    return _get(KEY_FETCH_TIMEOUT)


def get_frontend_refresh_seconds_raw() -> str:
    return _get(KEY_FRONTEND_REFRESH)


def get_min_confidence_raw() -> str:
    return _get(KEY_MIN_CONFIDENCE)


def get_require_source_url_raw() -> str:
    return _get(KEY_REQUIRE_SOURCE_URL)


def get_allow_unresolved_raw() -> str:
    return _get(KEY_ALLOW_UNRESOLVED)


def get_max_items_per_feed_raw() -> str:
    return _get(KEY_MAX_ITEMS_PER_FEED)


def get_max_post_age_days_raw() -> str:
    return _get(KEY_MAX_POST_AGE_DAYS)


def get_keywords_strong_raw() -> str:
    return _get(KEY_KEYWORDS_STRONG)


def get_keywords_context_raw() -> str:
    return _get(KEY_KEYWORDS_CONTEXT)


def get_keywords_weak_raw() -> str:
    return _get(KEY_KEYWORDS_WEAK)


def get_place_aliases_json_raw() -> str:
    return _get(KEY_PLACE_ALIASES_JSON)


def get_source_name_overrides_json_raw() -> str:
    return _get(KEY_SOURCE_NAME_OVERRIDES_JSON)


def save_all(data: dict):
    """Persist a dict of {key: raw_string_value} to the DB."""
    for key, value in data.items():
        if key in _DEFAULTS:
            set_setting(key, value)


def get_all_raw() -> dict:
    """Return all protest settings as raw strings (for admin UI)."""
    return {key: _get(key) for key in _DEFAULTS}
