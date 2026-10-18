"""Plain page fetch for a creator's link page or website. Polite by default (see http.SLEEP)."""
import re

from .http import call, pace


def fetch(url):
    pace()
    if not re.match(r"https?://", url or ""):
        url = "https://" + (url or "")
    s, t = call(url, raw=True, timeout=20)
    return s, t or ""
