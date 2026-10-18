"""Web search through Serper. 1 credit per query of up to 10 results."""
import re

from .. import ledger
from .http import call, env

EMAIL_RX = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,}")
FOLLOW_RX = re.compile(r"([\d.,]+\s?[KMkm]?)\+?\s+Followers?\b", re.I)


def available():
    return bool(env("SERPER_API_KEY"))


def to_int(s):
    s = (s or "").strip().replace(",", "")
    m = 1
    if s[-1:] in "Kk":
        m, s = 1000, s[:-1]
    elif s[-1:] in "Mm":
        m, s = 1000000, s[:-1]
    try:
        return int(float(s) * m)
    except ValueError:
        return None


def search(query, gl="gb", stage="discover"):
    """Returns {"error", "rows": [{link, title, snippet}]}. Retries once on a connection error."""
    ledger.check("serper", 1)
    for attempt in (1, 2):
        s, d = call("https://google.serper.dev/search", {"X-API-KEY": env("SERPER_API_KEY")}, {"q": query, "gl": gl, "num": 10}, timeout=40)
        if s == 200:
            ledger.charge("serper", d.get("credits") or 1, stage, "search")
            return {"error": None, "rows": [{"link": o.get("link") or "", "title": o.get("title") or "", "snippet": o.get("snippet") or ""} for o in d.get("organic") or []]}
    return {"error": "http %s %s" % (s, (d or {}).get("_error", "")[:120]), "rows": []}
