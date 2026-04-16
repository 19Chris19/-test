from __future__ import annotations

from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

TRACKING_PARAMS = {
    "utm_source",
    "utm_medium",
    "utm_campaign",
    "utm_term",
    "utm_content",
    "utm_id",
    "fbclid",
    "gclid",
}


def canonicalize_url(url: str) -> str:
    parsed = urlparse(url.strip())
    clean_query = [
        (key, value) for key, value in parse_qsl(parsed.query, keep_blank_values=True)
        if key.lower() not in TRACKING_PARAMS
    ]
    rebuilt = parsed._replace(query=urlencode(clean_query, doseq=True), fragment="")
    return urlunparse(rebuilt)
