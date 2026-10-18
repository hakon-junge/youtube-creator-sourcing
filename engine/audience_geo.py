"""Audience geography: where a creator's audience is, estimated from public signals. Free.

Nobody outside the channel can see YouTube's audience-country numbers (YouTube Studio shows them only to
the owner), so this is an estimate, built the way the paid audience tools build theirs and shown with
its sources and a confidence. Four independent signals, each from the commenters, the visible part of
an audience, plus the creator:

  1. commenter countries   the country set on commenters' own channels (API only; about 5% set one,
                           so it needs a few hundred commenters to say anything)
  2. comment times         when the audience comments: a mix of time zones fitted to the hours of the
                           day comments arrive (API only; the first 12 hours after upload are left out)
  3. dialect and places    spelling, words, currency, shops and place names in the comments
  4. creator               the country set on the channel, and the about text and titles

Known limit: the activity curve is a generic guess. UK audiences showed 10-45% "Asia-Pacific" in tests
(late-night comments), which under-counts the UK. Every estimate keeps its comment-hour totals so the
curve can be fitted from real runs.

City targets (London, New York) can only be read from place mentions, so a city result is a signal
with a count, never a percentage. Only totals are kept: nothing is stored per commenter.

Config (all optional, under geo):
  audience_target:
    countries: [GB]        # defaults to geo.markets
    min_share: 0.5         # the share of the audience that should be in those countries
    city: London           # optional hyperlocal target
    city_markers: []       # extra words for that city (neighbourhoods, local slang)
    action: flag           # flag (default) | reject: reject only on a clear miss with medium or high confidence
  audience_videos: 3       # videos sampled for the estimate (about 2 quota units each)
"""
import math
import re
from collections import Counter
from datetime import datetime, timezone

# Time-zone regions: (standard UTC offset, summer offset, summer months, member countries)
NORTH_SUMMER = range(4, 11)   # April-October
SOUTH_SUMMER = (10, 11, 12, 1, 2, 3)
REGIONS = {
    "UK, Ireland, Portugal": (0, 1, NORTH_SUMMER, {"GB", "IE", "PT"}),
    "Central Europe": (1, 2, NORTH_SUMMER, {"DE", "FR", "NL", "BE", "ES", "IT", "AT", "CH", "SE", "NO", "DK", "PL", "CZ", "HU", "NG"}),
    "Eastern Europe, Middle East": (2, 3, NORTH_SUMMER, {"FI", "GR", "RO", "BG", "UA", "TR", "IL", "EG", "ZA", "KE", "SA", "AE"}),
    "South Asia": (5.5, 5.5, (), {"IN", "PK", "BD", "LK"}),
    "South-East Asia": (8, 8, (), {"PH", "SG", "MY", "ID", "TH", "VN", "HK", "CN", "TW"}),
    "Australia, NZ": (10, 11, SOUTH_SUMMER, {"AU", "NZ"}),
    "US/Canada East": (-5, -4, NORTH_SUMMER, {"US", "CA"}),
    "US/Canada Central": (-6, -5, NORTH_SUMMER, {"US", "CA", "MX"}),
    "US/Canada West": (-8, -7, NORTH_SUMMER, {"US", "CA"}),
    "South America": (-3, -3, (), {"BR", "AR", "CL", "UY"}),
}
# Neighbouring time zones are only an hour or two apart, so the fit is read at continent level
COARSE = {"Europe and Africa": ("UK, Ireland, Portugal", "Central Europe", "Eastern Europe, Middle East"),
          "the Americas": ("US/Canada East", "US/Canada Central", "US/Canada West", "South America"),
          "Asia-Pacific": ("South Asia", "South-East Asia", "Australia, NZ")}
COARSE_OF = {r: c for c, rs in COARSE.items() for r in rs}

# When people comment, by local hour (a typical social-media day: quiet at night, peaking in the evening)
ACTIVITY = [2.0, 1.2, 0.7, 0.5, 0.4, 0.6, 1.2, 2.2, 3.0, 3.4, 3.6, 3.8, 4.0, 4.0, 4.0, 4.2, 4.5, 5.0, 5.4, 5.8, 6.0, 5.6, 4.6, 3.2]
_tot = sum(ACTIVITY)
ACTIVITY = [a / _tot for a in ACTIVITY]

# Dialect, money, shops and institutions people mention in passing. Shared words (mate, cheers) are left out.
DIALECT = {  # words specific to one country; spellings shared across the Commonwealth (mum, colour) are left out
    "GB": r"£|\bquid\b|\bfiver\b|\btenner\b|\btesco\b|\bsainsbury|\basda\b|\bmorrisons\b|\bwaitrose\b|\bm&s\b|\bprimark\b|\bnhs\b|\bcouncil tax\b|\bhmrc\b|\bisa\b|\bcuppa\b|\btelly\b|\bnappies\b|\bhoover(ing)?\b|\b(uk|britain|british|england|scotland|scottish|wales|welsh|yorkshire|manchester|birmingham|glasgow|london)\b",
    "US": r"\bmom(s|my)?\b|\bfavorite|\bcolor\b|\bneighbor|\$\d|\bbucks\b|\bwalmart\b|\bcostco\b|\bkroger\b|\btrader joe|\bwhole foods\b|\bwalgreens\b|\bcvs\b|\b401k\b|\broth ira\b|\bmedicaid\b|\by'?all\b|\bdiapers\b|\b(usa|america|american|stateside)\b|\b(texas|florida|california|ohio|georgia|michigan|arizona|carolina|new york)\b",
    "CA": r"\bcanadian tire\b|\bloblaws?\b|\bno frills\b|\btim hortons\b|\btimmies\b|\bloonie|\btoonie|\btfsa\b|\brrsp\b|\b(canada|canadian|ontario|quebec|alberta|toronto|vancouver|calgary|montreal|ottawa)\b",
    "AU": r"\bwoolies\b|\bcoles\b|\bbunnings\b|\barvo\b|\bsuperannuation\b|\bcentrelink\b|\b(australia|aussie|sydney|melbourne|brisbane|perth|adelaide|queensland)\b",
    "IE": r"\bdunnes\b|\b(ireland|irish|dublin|cork|galway)\b",
    "IN": r"₹|\brupees?\b|\blakh\b|\bcrore\b|\b(india|indian|mumbai|delhi|bangalore|bengaluru|hyderabad|chennai)\b",
}
DIALECT_RX = {k: re.compile(v, re.I) for k, v in DIALECT.items()}
CITIES = {
    "london": r"\blondon(er|ers)?\b|\bcroydon\b|\bhackney\b|\bcamden\b|\bbrixton\b|\bislington\b|\bpeckham\b|\bshoreditch\b|\bwimbledon\b|\bclapham\b|\bstratford\b|\bwalthamstow\b|\btfl\b|\bthe tube\b|\boyster card\b|\bzone [1-6]\b",
    "new york": r"\bnew york\b|\bnyc\b|\bmanhattan\b|\bbrooklyn\b|\bqueens\b|\bthe bronx\b|\bstaten island\b|\bharlem\b|\bastoria\b|\bwilliamsburg\b|\bthe mta\b",
    "manchester": r"\bmanchester\b|\bmanc\b|\bsalford\b|\bstockport\b",
    "toronto": r"\btoronto\b|\bthe 6ix\b|\bgta\b|\bscarborough\b|\bmississauga\b|\bttc\b",
    "los angeles": r"\blos angeles\b|\b(la|l\.a\.) traffic\b|\bhollywood\b|\bsanta monica\b|\bpasadena\b",
    "sydney": r"\bsydney\b|\bbondi\b|\bparramatta\b",
}
COUNTRY_NAMES = {"GB": "the UK", "US": "the US", "CA": "Canada", "AU": "Australia", "IE": "Ireland", "IN": "India"}


def target(cfg):
    g = cfg.get("geo") or {}
    t = dict(g.get("audience_target") or {})
    t["countries"] = [c.upper() for c in (t.get("countries") or g.get("markets") or [])]
    t.setdefault("min_share", 0.5)
    t.setdefault("action", "flag")
    if t.get("city"):
        extra = "|".join(re.escape(w) for w in t.get("city_markers") or [])
        base = CITIES.get(t["city"].lower(), r"\b%s\b" % re.escape(t["city"].lower()))
        t["city_rx"] = re.compile(base + ("|" + extra if extra else ""), re.I)
    return t


def _offset(region, month):
    std, summer, months, _ = REGIONS[region]
    return summer if month in months else std


def time_mix(stamps, iters=300):
    """Fit a mix of time-zone regions to the UTC times comments were posted. Returns ({region: share}, n)."""
    if len(stamps) < 40:
        return {}, len(stamps)
    names = list(REGIONS)
    # expected share of a region's comments in each UTC hour, using each comment's own month for summer time
    rows = []
    for ts in stamps:
        h, m = ts.hour + ts.minute / 60.0, ts.month
        row = []
        for r in names:
            local = (h + _offset(r, m)) % 24
            lo, frac = int(local), local - int(local)
            row.append(ACTIVITY[lo] * (1 - frac) + ACTIVITY[(lo + 1) % 24] * frac)
        rows.append(row)
    w = [1.0 / len(names)] * len(names)
    for _ in range(iters):  # EM for the mixture weights
        acc = [0.0] * len(names)
        for row in rows:
            p = [w[i] * row[i] for i in range(len(names))]
            s = sum(p) or 1e-12
            for i in range(len(names)):
                acc[i] += p[i] / s
        w = [a / len(rows) for a in acc]
    return {names[i]: round(w[i], 3) for i in range(len(names)) if w[i] >= 0.01}, len(stamps)


def dialect_counts(texts):
    by = Counter()
    for t in texts:
        for c, rx in DIALECT_RX.items():
            if rx.search(t or ""):
                by[c] += 1
    return by


def estimate(cfg, comments, commenter_countries, meta, titles, bio, source):
    """comments: [{text, ts (aware datetime or None)}]; commenter_countries: Counter of ISO codes (None = not set)."""
    t = target(cfg)
    tc = set(t["countries"])
    signals, parts = [], []

    # 1. commenter countries
    known = {k: v for k, v in commenter_countries.items() if k}
    n_known = sum(known.values())
    n_prof = sum(commenter_countries.values())
    if n_known:
        share = sum(v for k, v in known.items() if k in tc) / n_known
        top = ", ".join("%s %d" % kv for kv in Counter(known).most_common(3))
        signals.append(("commenter countries", share, min(1.0, n_known / 20.0) * 1.0))
        parts.append("%d of %d commenters with a country on their channel are in %s (%s; %d profiled)" % (
            sum(v for k, v in known.items() if k in tc), n_known, "/".join(sorted(tc)), top, n_prof))
    elif n_prof:
        parts.append("none of %d commenters profiled show a country" % n_prof)

    # 2. comment times
    stamps = [c["ts"] for c in comments if c.get("ts")]
    mix, n_ts = time_mix(stamps)
    if mix:
        coarse = Counter()
        for r, v in mix.items():
            coarse[COARSE_OF[r]] += v
        want = {COARSE_OF[r] for r in REGIONS if REGIONS[r][3] & tc}
        tz_share = sum(v for c, v in coarse.items() if c in want)
        top = ", ".join("%s %d%%" % (c, round(100 * v)) for c, v in coarse.most_common(3) if v >= 0.05)
        # a continent holds many countries: this mainly rules audiences out, so it weighs less than the others
        signals.append(("comment times", tz_share, min(1.0, n_ts / 150.0) * 0.5))
        parts.append("comment times fit %s (%d comments)" % (top, n_ts))
        mix = dict(coarse)
    elif source == "api":
        parts.append("too few dated comments for a time-zone fit (%d)" % n_ts)
    else:
        parts.append("no comment times without an API key")

    # 3. dialect and places
    texts = [c.get("text") or "" for c in comments]
    dc = dialect_counts(texts)
    n_d = sum(dc.values())
    if n_d:
        share = sum(v for k, v in dc.items() if k in tc) / n_d
        signals.append(("dialect and places", share, min(1.0, n_d / 15.0) * 0.8))
        parts.append("words and places in comments: %s" % ", ".join("%s %d" % (COUNTRY_NAMES.get(k, k), v) for k, v in dc.most_common(4)))

    # 4. creator
    country = (meta.get("country") or "").upper()
    blob = " ".join([bio or ""] + list(titles or []))
    cdc = dialect_counts([blob])
    if country:  # what the creator set on the channel: a prior, easily outweighed by what the commenters show
        signals.append(("creator", 1.0 if country in tc else 0.15, 0.25))
        parts.append("channel country %s" % country)
    elif cdc:
        signals.append(("creator", 1.0 if set(cdc) & tc else 0.2, 0.2))
        parts.append("about text and titles point to %s" % "/".join(COUNTRY_NAMES.get(k, k) for k in cdc))

    if not signals:
        return {"target": sorted(tc), "estimate": None, "confidence": "none", "parts": parts,
                "summary": "Audience geography: not enough public signal to estimate. Ask for a YouTube Studio audience screenshot."}
    wsum = sum(w for _, _, w in signals)
    est = sum(s * w for _, s, w in signals) / wsum
    strong = [s for name, s, w in signals if w >= 0.5 and name != "creator"]
    agree = len(strong) >= 2 and max(strong) - min(strong) <= 0.25
    conf = "high" if agree and wsum >= 1.8 else "medium" if (agree or (strong and wsum >= 1.0)) else "low"
    spread = {"high": 0.1, "medium": 0.15, "low": 0.25}[conf]
    lo, hi = max(0.0, est - spread), min(1.0, est + spread)

    city = None
    if t.get("city"):
        rx = t["city_rx"]
        c_comments = sum(1 for x in texts if rx.search(x))
        c_titles = sum(1 for x in titles or [] if rx.search(x))
        c_bio = bool(rx.search(bio or ""))
        level = "strong" if c_bio or c_titles >= 3 or c_comments >= 5 else "some" if (c_titles or c_comments >= 2) else "none"
        city = {"city": t["city"], "comments": c_comments, "titles": c_titles, "bio": c_bio, "signal": level}
        parts.append("%s named in %d comments, %d recent titles%s" % (t["city"], c_comments, c_titles, ", and the about text" if c_bio else ""))

    names = "/".join(COUNTRY_NAMES.get(c, c) for c in sorted(tc)) or "the target"
    verdict = "meets" if lo >= t["min_share"] else "misses" if hi < t["min_share"] else "unclear"
    summary = "Audience geography (estimate, %s confidence): about %d%% in %s (%d-%d%%), target %d%%: %s. %s." % (
        conf, round(100 * est), names, round(100 * lo), round(100 * hi), round(100 * t["min_share"]),
        {"meets": "meets it", "misses": "misses it", "unclear": "too close to call"}[verdict], ("; ".join(parts))[:1].upper() + ("; ".join(parts))[1:])
    if city:
        summary += " City signal for %s: %s." % (city["city"], city["signal"])
    summary += " Verify with a YouTube Studio audience screenshot before a deal."
    return {"target": sorted(tc), "min_share": t["min_share"], "estimate": round(est, 2), "range": [round(lo, 2), round(hi, 2)],
            "confidence": conf, "verdict": verdict, "signals": [{"name": n, "share": round(s, 2), "weight": round(w, 2)} for n, s, w in signals],
            "time_mix": mix, "city": city, "parts": parts, "summary": summary, "action": t["action"],
            # totals only, kept so the activity curve can be calibrated from real runs later
            "comment_hours_utc": [sum(1 for x in stamps if x.hour == h) for h in range(24)],
            "commenter_country_totals": {k or "none": v for k, v in commenter_countries.items()}}


def parse_ts(s):
    try:
        return datetime.strptime(s[:19], "%Y-%m-%dT%H:%M:%S").replace(tzinfo=timezone.utc)
    except Exception:
        return None
