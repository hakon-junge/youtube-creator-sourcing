"""Gates, relevance classifier, video stats and brand relationships.

Cheap before expensive:
  meta_gate()      free: handle + search snippet / caption
  channel gates    the channel record (band, country, about text)
  history gates    the upload history (dormancy, long-form median views, niche share, sponsorships)
Reach never rescues fit. Hard gates reject; everything else is a signal that ranks or flags.
"""
import re
import statistics
import time
from collections import Counter

import yaml


def _rx(s):
    # YAML folded scalars join lines with spaces; strip whitespace around pipes only
    return re.compile(re.sub(r"\s*\|\s*", "|", (s or "").strip()), re.I | re.S)


def _terms_rx(terms):
    return re.compile("|".join(re.escape(t.lower()) for t in terms if t), re.I) if terms else None


class Cfg:
    def __init__(self, path):
        with open(path) as f:
            self.raw = yaml.safe_load(f)
        c = self.raw
        self.core = _rx(c["core_rx"])
        self.domain = _rx(c["domain_rx"])  # the DOMAIN signal core_rx requires
        self.off_hard = _rx(c["off_hard_rx"])
        self.off_soft = _rx(c["off_soft_rx"])
        self.sponsor_marker = _rx(c["sponsor_marker_rx"])
        self.corporate = _rx(c["corporate_rx"])
        self.org = _rx(c.get("org_rx") or ORG_RX)
        self.business_categories = [x.lower() for x in c.get("business_categories") or BUSINESS_CATEGORIES]
        self.corp_names = [x.lower() for x in c.get("corporate_names") or []]
        self.brand_handles = [x.lower() for x in c.get("brand_handles") or []]
        self.partners = [x.lower().lstrip("@") for x in c.get("existing_partners") or []]
        self.seed_ids = {}  # channel id -> name of the operator's imported top creators (engine/seeds.py)
        g = c.get("geo") or {}
        self.home_rx = _rx(g["home_markers_rx"]) if g.get("home_markers_rx") else UK_RX
        self.out_rx = _rx(g["out_markers_rx"]) if g.get("out_markers_rx") else OUT_RX
        self.home_flags = tuple("".join(chr(0x1F1E6 + ord(ch) - 65) for ch in cc.upper()) for cc in g.get("markets") or [])
        # every brand we track a relationship with: own, direct, indirect
        self.brands = [{"name": c["company"], "kind": "own", "rx": _terms_rx(c.get("brand_terms")), "handles": self.brand_handles, "edge": None}]
        for kind in ("direct", "indirect"):
            for b in c.get(kind + "_competitors") or []:
                self.brands.append({"name": b["name"], "kind": kind, "rx": _terms_rx(b.get("terms")),
                                    "handles": [h.lower() for h in b.get("handles") or []], "edge": b.get("edge")})

    def __getitem__(self, k):
        return self.raw[k]

    def get(self, k, default=None):
        return self.raw.get(k, default)


# An organisation speaking, not a person: used on the bio and on link-page titles.
ORG_RX = r"\\b(we|our team)\\b.{0,30}\\b(sell|ship|deliver|stock|manufacture|are a (company|brand|business|team of))|to your door|order (now|today|online)|shop (now|our)|our (range|products|collection) (are|is|include)|free delivery|trustpilot|\\bdirectory\\b|stockists|wholesale|find a retailer|find us at|\\bdelivery\\b.{0,20}(india|worldwide|nationwide)|pioneer .{0,30}company|(is|are) (a|an|the) .{0,40}(company|brand|retailer|manufacturer)\\b|official (youtube )?channel of"
BUSINESS_CATEGORIES = ["Product/service", "Brand", "Company", "Shopping & retail", "Retail company", "E-commerce website",
                       "Local business", "Media/news company", "Nonprofit organization", "Charity organization"]


def looks_organisation(cfg, bio, link_titles, category):
    """A business behind the account, read from the full bio, the link page and the platform's own category."""
    if category and category.lower() in cfg.business_categories:
        return "business_category:%s" % category
    for text in (bio or "", " | ".join(link_titles or [])):
        m = cfg.org.search(text)
        if m:
            return "organisation_marker:%s" % m.group(0)[:40]
    return None


def _norm(s):
    return re.sub(r"[^a-z0-9]", "", (s or "").lower())


def is_own_or_competitor(cfg, handle, name=""):
    """The account IS a tracked brand (own or competitor). Using or promoting one is not this."""
    h, n = _norm(handle), _norm(name)
    for b in cfg.brands:
        for bh in b["handles"]:
            bh = _norm(bh)
            if h == bh or (h.startswith(bh) and h[len(bh):] in ("uk", "official", "hq", "ie", "nl", "de", "shop", "store", "app")) or n == bh:
                return "own_brand" if b["kind"] == "own" else "competitor_account"
        bn = _norm(b["name"])  # the brand's name at the start of a handle or as the display name: its own account
        if len(bn) >= 6 and (h.startswith(bn) or n == bn or n.startswith(bn)):
            return "own_brand" if b["kind"] == "own" else "competitor_account"
    return None


def looks_corporate(cfg, name, handle, bio=""):
    n = (name or "").lower()
    for c in cfg.corp_names:
        if n == c or n.startswith(c + " ") or _norm(handle).startswith(_norm(c)):
            return "corporate_name"
    if cfg.corporate.search(name or "") or cfg.corporate.search(bio or ""):
        return "corporate_marker"
    return None


def classify_relevance(cfg, text):
    """Bucket on free text (name + bio + captions): core, domain, off, neutral."""
    t = text or ""
    m = cfg.off_hard.search(t)
    if m:
        return "off", "off_hard:" + m.group(0)
    core = cfg.core.search(t) if cfg.domain.search(t) else None
    m = cfg.off_soft.search(t)
    if m and not core:
        return "off", "off_soft:" + m.group(0)
    if core:
        return "core", "core:" + core.group(0)
    m = cfg.domain.search(t)
    if m:
        return "domain", "domain:" + m.group(0)
    return "neutral", "no domain signal"


def meta_gate(cfg, handle, text):
    """Free reject on the search hit alone. Returns (verdict, reason)."""
    if handle in cfg.partners:
        return "reject", "existing_partner"
    oc = is_own_or_competitor(cfg, handle)
    if oc:
        return "reject", oc
    m = cfg.off_hard.search(text or "")
    if m:
        return "reject", "off_hard:" + m.group(0)
    return "pass", ""


def domain_share(cfg, captions):
    """Share of recent captions carrying the domain signal. One video on the topic does not make a topic creator."""
    caps = [c for c in captions if c]
    return round(sum(1 for c in caps if cfg.domain.search(c)) / len(caps), 2) if caps else 0.0


# ---------------- language / geography ----------------

STOP = {
    "de": "und der die das ist nicht ich mit ein eine auch hund sehr zu auf für mein".split(),
    "fr": "et le la les est pas je avec un une des pour mon chien très que du".split(),
    "en": "the and is not with you this that for my are very was have it".split(),
    "nl": "en de het is niet ik met een ook hond zeer voor mijn".split(),
    "es": "y el la los es no con un una para mi perro muy que".split(),
    "pt": "e o a os é não com um uma para meu cão muito que".split(),
    "it": "e il la è non con un una per mio cane molto che".split(),
    "pl": "i w nie na się jest że to jak do mam ale czy tak dla już".split(),
    "hi": "hai nahi nhi kya bhai aur ke ka ki ko toh mere bhi kabhi hota raha".split(),  # Hindi written in Latin script
    "sv": "och att det som är för med har inte jag på en av den till min hund också så".split(),
}
SCRIPT_RX = {"cyr": re.compile(r"[Ѐ-ӿ]"), "arab": re.compile(r"[؀-ۿ]"), "deva": re.compile(r"[ऀ-ॿ]"),
             "cjk": re.compile(r"[぀-ヿ一-鿿가-힯]"), "thai": re.compile(r"[฀-๿]")}
UK_RX = re.compile(r"£|🏴|\bmum\b|\bcolour|\bfavourite|\bbehaviour|\bcheers\b|\blovely\b|\bquid\b|\bwhilst\b|\bnhs\b|\bbritish\b|\buk\b|\bu\.k\b|"
                   r"\bengland\b|\blondon\b|\bscotland\b|\bscottish\b|\bwales\b|\bwelsh\b|\bmanchester\b|\byorkshire\b|\bcornwall\b|\bdevon\b|\bessex\b|\bkent\b|"
                   r"\bhampshire\b|\bmidlands\b|\bderbyshire\b|\blancashire\b|\bsussex\b|\bdorset\b|\bsomerset\b|\bcheshire\b|\bcumbria\b|\bsuffolk\b|\bwiltshire\b|\bnottingham\b|\bsheffield\b|\bbrighton\b|\bbristol\b|\bleeds\b|\bliverpool\b|\bbirmingham\b|\bglasgow\b|\bedinburgh\b|\bcardiff\b|\bnewcastle\b|\bnorfolk\b|\bsurrey\b|\bireland\b|\birish\b|\bdublin\b|\bbelfast\b", re.I)
OUT_RX = re.compile(r"\$\d|\bmom\b|\bcolor\b|\bfavorite\b|\bbehavior\b|\by'?all\b|\bvacation\b|\bpetco\b|\bpetsmart\b|\bchewy\b|\busa\b|\bnyc\b|"
                    r"\bcanada\b|\bcanadian\b|\baustralia\b|\baussie\b|\bsydney\b|\bmelbourne\b|\btoronto\b|\btexas\b|\bflorida\b|\bcalifornia\b|\bohio\b|\bnew york\b|\bchicago\b|\bseattle\b|\blos angeles\b|"
                    r"\bspain\b|\bvalencia\b|\bmadrid\b|\bbarcelona\b|\bmarbella\b|\bsweden\b|\bg[öo]teborg\b|\bgothenburg\b|\bstockholm\b|\bindia\b|\bgermany\b|\bberlin\b|"
                    r"\bfrance\b|\bparis\b|\bnetherlands\b|\bamsterdam\b|\bdubai\b|\bitaly\b|\bportugal\b|\blisbon\b|living abroad", re.I)


def detect_lang(text):
    t = (text or "").lower()
    for s, rx in SCRIPT_RX.items():
        if len(rx.findall(t)) >= 3:
            return s
    words = re.findall(r"[a-zåäöæøéèêàçüßñ']+", t)
    if len(words) < 3:
        return None
    best, score = None, 0
    ws = Counter(words)
    for lang, sw in STOP.items():
        s = sum(ws[w] for w in sw)
        if s > score:
            best, score = lang, s
    return best if score >= 1 else None


FLAG_RX = re.compile("[\U0001F1E6-\U0001F1FF]{2}")


def markers(cfg, text):
    """(home, out) marker counts. Home and out vocabularies come from the brand config (geo.home_markers_rx,
    geo.out_markers_rx); the built-in defaults are for a UK and Ireland market. Any flag emoji that is
    not one of the brand's markets counts as out."""
    t = text or ""
    flags = FLAG_RX.findall(t)
    bare = FLAG_RX.sub(" ", t)
    return (len(cfg.home_rx.findall(bare)) + sum(1 for f in flags if f in cfg.home_flags),
            len(cfg.out_rx.findall(bare)) + sum(1 for f in flags if f not in cfg.home_flags))


def geo_signal(cfg, texts, bio=""):
    """Market fit from text the creator wrote. English is ambiguous (UK vs elsewhere): flagged, never auto-passed.

    The bio is where creators say where they are, so a location there decides it on its own.
    """
    blob = " ".join(t for t in texts if t)
    lang = detect_lang(blob)
    home, out = markers(cfg, blob)
    bio_home, bio_out = markers(cfg, bio)
    if lang and lang not in cfg["geo"]["market_langs"]:
        verdict = "out"
    elif bio_out and not bio_home:
        verdict = "out"
    elif bio_home and not bio_out:
        verdict = "market"
    elif out >= 2 and home == 0:
        verdict = "out"
    elif home >= 1 and home > out:
        verdict = "market"
    else:
        verdict = "ambiguous"
    return {"lang": lang, "home_markers": home, "out_markers": out, "bio_home": bio_home, "bio_out": bio_out, "verdict": verdict}


# ---------------- video health ----------------

def post_stats(cfg, posts, followers):
    """Dormancy, cadence, engagement and (when view counts are known) the organic median of video views.

    Pinned posts and posts under `min_post_age_days` old stay out of the medians: a pinned post is the
    creator's best, and a new one has not collected its numbers yet. A video counts as likely boosted
    when its views are far above the creator's own median while its like rate is well below theirs;
    it is left out of the organic median and listed. That is an inference from public numbers.
    Engagement rate here is per follower; phase1 replaces it with a per-view rate for YouTube.
    """
    allp = sorted([p for p in posts if p.get("ts")], key=lambda p: -p["ts"])
    if not allp:
        return None
    now = time.time()
    newest = max(p["ts"] for p in allp)
    settled = [p for p in allp if not p.get("pinned") and now - p["ts"] >= cfg.get("min_post_age_days", 3) * 86400]
    ps = (settled if len(settled) >= 4 else [p for p in allp if not p.get("pinned")] or allp)[: cfg["recent_posts"]]
    likes = [p["likes"] for p in ps if p.get("likes") is not None]
    comms = [p["comments"] for p in ps if p.get("comments") is not None]
    vids = [p for p in ps if p.get("views")]
    out = {
        "n": len(ps), "days_since_last": round((now - newest) / 86400.0, 1),
        "posts_per_week": round(len(ps) / max((ps[0]["ts"] - ps[-1]["ts"]) / 86400.0, 1.0) * 7, 1),
        "median_likes": int(statistics.median(likes)) if likes else None,
        "median_comments": int(statistics.median(comms)) if comms else 0,
        "engagement_rate": round(statistics.median([((p.get("likes") or 0) + (p.get("comments") or 0)) / followers for p in ps]), 4) if followers else None,
        "videos_with_views": len(vids), "median_views_all": None, "median_views_organic": None, "max_views": None, "likely_boosted": [],
    }
    if len(vids) >= 3:
        views = [p["views"] for p in vids]
        med = statistics.median(views)
        rates = [(p.get("likes") or 0) / p["views"] for p in vids]
        med_rate = statistics.median(rates)
        boosted = [p["id"] for p in vids if p["views"] > 8 * med and med_rate and (p.get("likes") or 0) / p["views"] < 0.5 * med_rate]
        organic = [p["views"] for p in vids if p["id"] not in boosted]
        out.update(median_views_all=int(med), median_views_organic=int(statistics.median(organic)) if organic else int(med), max_views=max(views), likely_boosted=boosted)
    return out


# ---------------- brand relationships ----------------

def relationships(cfg, posts):
    """Per tracked brand: how many of the creator's posts mention it, and how many carry a paid marker.

    posts = [{caption, ts, url, paid_flag}]. 4+ paid posts for one brand = likely working (the brand came
    back after a test). Posts bunched inside 21 days are marked as a bundle. Only the posts the engine
    has seen are counted, so a low count is a floor, not the creator's full history.
    """
    out = []
    now = time.time()
    for b in cfg.brands:
        if not b["rx"]:
            continue
        hits = [p for p in posts if b["rx"].search(p.get("caption") or "")]
        if not hits:
            continue
        paid = [p for p in hits if p.get("paid_flag") or cfg.sponsor_marker.search(p.get("caption") or "")]
        ts = sorted(p["ts"] for p in hits if p.get("ts"))
        last_days = round((now - ts[-1]) / 86400.0) if ts else None
        span = round((ts[-1] - ts[0]) / 86400.0) if len(ts) > 1 else 0
        out.append({
            "brand": b["name"], "kind": b["kind"], "edge": b["edge"], "posts": len(hits), "paid_posts": len(paid),
            "last_days_ago": last_days, "span_days": span,
            "status": "date unknown" if last_days is None else ("active" if last_days <= 90 else "lapsed"),
            "bundle": len(paid) >= 4 and span <= 21,
            "strength": "likely_working" if len(paid) >= 4 else ("test_phase" if paid else "mention_only"),
            "urls": [p.get("url") for p in hits][:4],
        })
    return out


# ---------------- promotion signals ----------------

PROMO_RX = re.compile(r"bundle|\bshop\b|\border\b|available (now|at|on)|link in (my )?bio|use (my )?code|discount|% ?off|sent (us|me)|gifted|thanks to @|have put together|everything you need", re.I)
MENTION_RX = re.compile(r"@[A-Za-z0-9_.]{2,}")

def is_promo(cfg, caption):
    """A post that promotes a brand: a paid marker, or a tagged account next to selling language."""
    c = caption or ""
    return bool(cfg.sponsor_marker.search(c) or (MENTION_RX.search(c) and PROMO_RX.search(c)))


def _reach(p):
    return p["views"] if p.get("views") else p.get("likes")


def is_paid(cfg, p):
    return bool(p.get("paid_flag") or is_promo(cfg, p.get("caption")))


def paid_vs_organic(cfg, posts):
    """Do this creator's promotional posts hold their audience? Median reach of promo posts against the rest.
    Reach is views where known, otherwise likes; the two groups are only compared on the same measure."""
    vs = [p for p in posts if _reach(p) is not None and not p.get("pinned")]
    use_views = sum(1 for p in vs if p.get("views")) >= max(3, len(vs) // 2)
    if use_views:
        vs = [p for p in vs if p.get("views")]
    val = (lambda p: p["views"]) if use_views else (lambda p: p.get("likes") or 0)
    paid = [val(p) for p in vs if is_paid(cfg, p)]
    org = [val(p) for p in vs if not is_paid(cfg, p)]
    base = {"paid_n": len(paid), "organic_n": len(org), "measure": "views" if use_views else "likes", "ratio": None}
    if len(paid) < 2 or len(org) < 3:
        return base
    pm, om = statistics.median(paid), statistics.median(org)
    return dict(base, paid_median=int(pm), organic_median=int(om), ratio=round(pm / om, 2) if om else None)


def promo_share(cfg, posts):
    ps = [p for p in posts if p.get("caption") or p.get("paid_flag")]
    return round(sum(1 for p in ps if is_paid(cfg, p)) / len(ps), 2) if ps else 0.0


def notable_posts(cfg, posts, stats):
    """Posts a reviewer will want to open: the outlier by views, and the promotional ones."""
    out, med = [], (stats or {}).get("median_views_organic") or 0
    vs = [p for p in posts if p.get("views")]
    top = max(vs, key=lambda p: p["views"], default=None)
    if top and med and top["views"] > 5 * med:
        out.append({"url": top["url"], "views": top["views"], "ts": top.get("ts"), "why": "highest views, %dx the organic median" % round(top["views"] / med),
                    "promo": is_paid(cfg, top)})
    for p in sorted([p for p in posts if is_paid(cfg, p)], key=lambda p: -(_reach(p) or 0))[:3]:
        if p["url"] not in [o["url"] for o in out]:
            out.append({"url": p["url"], "views": p.get("views"), "likes": p.get("likes"), "ts": p.get("ts"),
                        "why": "paid partnership" + (" with " + ", ".join(p["sponsors"]) if p.get("sponsors") else "") if p.get("paid_flag") else "promotional post", "promo": True})
    return out


def link_page_stats(html):
    """How many links the creator lists on a Linktree page. None when the page is not one we can read.

    Linktree ships its own partner and script hosts in every page, so counting raw URLs is wrong;
    only the creator's own link list in the page data is counted.
    """
    m = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', html or "", re.S)
    if not m:
        return None
    try:
        import json
        data = json.loads(m.group(1))
    except ValueError:
        return None
    found = []

    def walk(o, depth=0):
        if depth > 8 or found:
            return
        if isinstance(o, dict):
            links = o.get("links")
            if isinstance(links, list) and links and all(isinstance(x, dict) for x in links) and any(x.get("url") for x in links):
                found.append(links)
                return
            for v in o.values():
                walk(v, depth + 1)
        elif isinstance(o, list):
            for v in o[:50]:
                walk(v, depth + 1)
    walk(data)
    if not found:
        return None
    links = [x for x in found[0] if x.get("url")]
    titles = [str(x.get("title") or "") for x in links]
    codes = sum(1 for t in titles if re.search(r"\bcode\b|% ?off|discount|\b[A-Z]{3,}\d{1,2}\b", t))
    return {"links": len(links), "codes": codes, "titles": [t[:40] for t in titles[:10]]}
