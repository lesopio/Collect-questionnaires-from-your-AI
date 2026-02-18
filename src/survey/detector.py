from __future__ import annotations

from urllib.parse import urlparse


def detect_platform(url: str) -> str:
    host = (urlparse(url).netloc or "").lower()
    if any(token in host for token in ("wjx", "wenjuan", "sojump")):
        return "wjx_like"
    if "forms.gle" in host or "docs.google.com" in host:
        return "google_forms"
    if "forms.office.com" in host:
        return "microsoft_forms"
    return "unknown"

