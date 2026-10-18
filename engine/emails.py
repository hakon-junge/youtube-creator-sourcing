"""Email ladder: find a public email for a creator, cheapest source first. Never guessed.

An email is ACCEPTED only when it sits on the creator's own profile or page, or matches their handle.
Anything else is kept as unverified and is never the send address without a human check.
Every email carries the URL it was read from.
"""
import re
import urllib.parse

from . import ledger, platform
from .providers import keyless, serper

EMAIL_RX = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,}")
JUNK_RX = re.compile(r"\.(png|jpe?g|webp|svg|gif|css|js)$|sentry|example\.|wixpress|@2x|@3x|noreply|no-reply|linktr\.ee$|@youtube\.|@beacons\.|@linktree\.", re.I)
FREE_RX = re.compile(r"@(gmail|googlemail|hotmail|outlook|yahoo|icloud|me|live|aol|proton|protonmail|gmx|web|btinternet|msn)\.", re.I)
MGMT_RX = re.compile(r"mgmt|management|talent|agency|agent|represent|\bpr@|@.*(mgmt|management|talent|agency)", re.I)
CONTACT_RX = re.compile(r'href="([^"]*(?:contact|about|work-with|collab|enquir|kontakt)[^"]*)"', re.I)


def _norm(s):
    return re.sub(r"[^a-z0-9]", "", (s or "").lower())


def clean(text):
    t = (text or "").replace("\\u0040", "@").replace("%40", "@").replace(" [at] ", "@").replace("(at)", "@")
    out = []
    for e in EMAIL_RX.findall(t):
        e = e.strip(".").lower()
        if not JUNK_RX.search(e) and e not in out:
            out.append(e)
    return out


def matches_handle(email, handle, name=""):
    """Local part and handle (or display name) share a 5+ character run."""
    local = _norm(email.split("@")[0])
    for ref in (_norm(handle), _norm(name)):
        if len(ref) < 4 or len(local) < 4:
            continue
        if ref in local or local in ref:
            return True
        for i in range(len(ref) - 4):
            if ref[i:i + 5] in local:
                return True
    return False


def kind(email):
    if MGMT_RX.search(email):
        return "management"
    return "personal" if FREE_RX.search(email) else "business"


def _hit(email, step, source_url, accepted):
    return {"email": email, "step": step, "source": source_url, "accepted": accepted, "type": kind(email)}


def ladder(cand, profile, allow_search=True, bio_page=None):
    """Returns (best, all_found, steps_tried). best is the first ACCEPTED email, else None."""
    handle, name = cand["handle"], (profile or {}).get("name", "")
    purl = platform.profile_url(handle)
    found, tried = [], []

    def done():
        best = next((f for f in found if f["accepted"]), None)
        return best, found, tried

    # step 1: discovery snippets. A profile hit is the creator's own bio; a post hit must match the handle.
    tried.append("snippet")
    for e in cand.get("snippet_emails") or []:
        ok = e["from"] == "profile" or matches_handle(e["email"], handle, name)
        found.append(_hit(e["email"], "snippet", e["url"], ok))
    # step 2: bio
    tried.append("bio")
    for e in clean((profile or {}).get("bio")):
        found.insert(0, _hit(e, "bio", purl, True))
    if any(f["accepted"] for f in found):
        return done()
    # step 3: link-in-bio page, then one contact page on the same site
    link = (profile or {}).get("bio_link")
    if link:
        tried.append("bio_link")
        s, page = bio_page if bio_page is not None else keyless.fetch(link)
        for e in clean(page):
            found.append(_hit(e, "bio_link", link, True))
        if not any(f["accepted"] for f in found) and page:
            base = link if re.match(r"https?://", link) else "https://" + link
            host = urllib.parse.urlparse(base).netloc
            for href in CONTACT_RX.findall(page)[:6]:
                u = urllib.parse.urljoin(base, href)
                if urllib.parse.urlparse(u).netloc == host and u.rstrip("/") != base.rstrip("/"):
                    tried.append("contact_page")
                    s2, p2 = keyless.fetch(u)
                    for e in clean(p2):
                        found.append(_hit(e, "contact_page", u, True))
                    break
    if any(f["accepted"] for f in found):
        return done()
    # step 5: one targeted search. Accepted only when the address matches the handle.
    if allow_search and serper.available() and ledger.allowed("serper", 1):
        tried.append("targeted_search")
        r = serper.search('"%s" youtube email OR contact OR "business enquiries" OR collab' % (name or handle), stage="email")
        for row in r["rows"]:
            for e in clean(row["title"] + " " + row["snippet"]):
                if e not in [f["email"] for f in found]:
                    found.append(_hit(e, "targeted_search", row["link"], matches_handle(e, handle, name)))
    return done()
