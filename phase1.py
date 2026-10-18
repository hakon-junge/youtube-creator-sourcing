"""Stages 1-3 for YouTube: discovery and gating, cheapest check first.

  python phase1.py --brand <slug> --dry-run     zero-cost preview of the query plan
  python phase1.py --brand <slug>               out/<brand>/<date>/results.json

Order per channel: title gate -> seen store -> channel record (subscriber band, country, about text,
organisation check) -> upload history (dormancy, long-form median views, niche share, sponsorship
history from descriptions) -> geography -> email ladder -> entry videos -> score.
With a YouTube Data API key a channel costs about 3 quota units; without one the engine reads
public pages and the RSS feed and sees 15 uploads instead of 50.
"""
import argparse
import copy
import os
import re
import sys
from collections import Counter
from datetime import date

from engine import emails, filters, ledger, platform, seeds, store
from engine.providers import yt
from engine.providers.http import call, pace

ROOT = os.path.dirname(os.path.abspath(__file__))
WEIGHTS = {"views": 20, "relevance": 15, "contact": 15, "audience": 25, "geography": 10, "brand_proof": 15}
STRICT_SPONSOR_RX = re.compile(r"sponsored by|is sponsored|for sponsoring|paid partnership|paid promotion|includes paid promotion|\#ad\b|\#sponsored|in partnership with|partnered with", re.I)
SPONSOR_NAME_RX = re.compile(r"(?:sponsored by|thanks to|thank you to|partnered with|in partnership with)\s+@?([A-Z][A-Za-z0-9&'.]+(?: [A-Z][A-Za-z0-9&'.]+){0,2})")
LATERAL = ("content", "seed", "lookalike")  # the lanes that start from the operator's own top videos and creators
URL_RX = re.compile(r"https?://[^\s)\]>\"']+")
SOCIAL_HOSTS = ("youtube.com", "youtu.be", "instagram.com", "tiktok.com", "facebook.com", "twitter.com", "x.com", "amzn.to", "amazon.", "bit.ly", "goo.gl", "discord.", "patreon.com", "twitch.tv", "spotify.com", "apple.com")


def log(*a):
    print(*a, flush=True)


def plan_queries(cfg):
    lanes, q = cfg["lanes"], []
    for t in lanes.get("keyword") or []:
        q.append(("keyword", t, None))
    if lanes.get("competitor_collab"):
        for b in cfg.brands:
            term = (b["rx"].pattern.split("|")[0].replace("\\", "")) if b["rx"] else b["name"]
            q.append(("competitor_collab", "%s %s" % (term, cfg.get("collab_suffix", "review")), b["name"]))
    return q[: cfg.get("max_searches", 14)]


def discover(cfg, c, queries, use_state):
    """One search per query. A candidate is a channel; the video that surfaced it is its entry video."""
    cands, qlog = {}, []
    for lane, q, brand in queries:
        # search is the one expensive API call (100 units). The keyless search returns the same kind of
        # result for nothing, so it is the default and the quota goes to channels and comments instead.
        if cfg.get("search_backend", "keyless") == "keyless":
            r = yt._k_search(q, cfg.get("results_per_search", 25))
            if r["error"] or not r["rows"]:
                r = yt.search(q, cfg.get("results_per_search", 25))
        else:
            r = yt.search(q, cfg.get("results_per_search", 25))
        for row in r["rows"]:
            d = cands.setdefault(row["channel_id"], {"channel_id": row["channel_id"], "name": row["channel"], "lanes": [], "entry_posts": [], "texts": [],
                                                    "snippet_emails": [], "collab_hits": []})
            d["lanes"].append(lane)
            d["texts"].append(row["title"])
            if lane in LATERAL and brand not in d.setdefault("seed_of", []):
                d["seed_of"].append(brand)
            post = {"url": platform.post_url(row["video_id"]), "caption": row["title"], "lane": lane, "query": q}
            (d["collab_hits"] if lane == "competitor_collab" else d["entry_posts"]).append(dict(post, brand=brand))
        qlog.append({"lane": lane, "query": q, "hits": len(r["rows"]), "error": r["error"]})
        log("  %-17s %2d hits  %s%s" % (lane, len(r["rows"]), q[:78], "  ERR " + r["error"] if r["error"] else ""))
        if use_state:
            store.log_query(c, q, len(r["rows"]))
    return cands, qlog


def bio_link(description):
    """The creator's own site or link page from the channel's about text, if it lists one."""
    for u in URL_RX.findall(description or ""):
        if not any(h in u.lower() for h in SOCIAL_HOSTS):
            return u.rstrip(".,")
    return None


def pick_entry_posts(cfg, cand, videos, rels):
    """Most relevant recent long-form video first, the discovery video as fallback. Never a sponsored-by-competitor one."""
    comp_urls = {u for r in rels if r["kind"] != "own" for u in r["urls"]}
    want_short = cand.get("_format") == "shorts"
    pool = {v["id"]: dict(v, source="recent") for v in videos if bool(v.get("is_short")) == want_short}
    for p in cand["entry_posts"]:
        key = platform.post_id(p["url"])
        pool[key] = dict(pool.get(key, {"url": p["url"], "caption": p["caption"]}), lane=p["lane"], source="discovery")
    scored = []
    for key, p in pool.items():
        cap = p.get("caption") or ""
        if p["url"] in comp_urls:
            continue
        s = (3 if cfg.core.search(cap) and cfg.domain.search(cap) else 1 if cfg.domain.search(cap) else 0)
        s += 2 if p.get("source") == "discovery" else 0
        scored.append((s, p.get("ts") or 0, p))
    scored.sort(key=lambda t: (-t[0], -t[1]))
    return [{"url": p["url"], "caption": (p.get("caption") or "")[:300], "views": p.get("views"), "likes": p.get("likes"), "comments": p.get("comments"),
             "ts": p.get("ts"), "source": p.get("source"), "relevance": s} for s, _, p in scored[:2] if s > 0]


def score(cfg, rec):
    """0-100. Six weighted parts plus penalties, clamped; every line of the breakdown is kept.

    Hard gates are already applied, so this only ranks. Weights can be overridden per brand
    (config `weights`). Comments carry the most weight: a creator nobody talks to does not convert.
    """
    W = dict(WEIGHTS, **(cfg.get("weights") or {}))
    pts, why = 0.0, []

    def add(n, label):
        nonlocal pts
        pts += n
        why.append("%+d %s" % (round(n), label))
    s = rec.get("stats") or {}
    mv, lo = s.get("median_views_organic"), cfg["target_views"][0]
    if mv is None:
        add(0, "views: not verified (fewer than 3 recent long-form videos)")
    else:
        add(W["views"] if mv >= lo else 0, "views: %s median %d" % (rec.get("format") or "long-form", mv))
        if mv >= cfg["target_views"][1]:
            add(5, "bonus: long-form median above the %d target" % cfg["target_views"][1])
    ds = rec.get("domain_share")
    share = 1.0 if ds is None or ds >= cfg.get("flag_domain_share", 0) else (0.5 if ds >= 0.3 else 0.2)
    base = {"core": 1.0, "domain": 0.5}.get(rec.get("bucket"), 0)
    add(W["relevance"] * base * share, "relevance: %s%s" % (rec.get("bucket"), "" if share == 1 else ", side theme (%d%% of recent titles)" % round(100 * (ds or 0))))
    add(W["contact"] if rec.get("email") else 0, "contact: %s" % ("email found" if rec.get("email") else "no email found"))
    au = rec.get("audience")
    if au:
        n = au["texture"]["n"]
        thin = n < 8
        add(W["audience"] * au["score"] / 100.0 * (0.5 if thin else 1.0), "audience: check scored %d on %d comments%s" % (au["score"], n, ", halved for a thin sample" if thin else ""))
    else:
        mc = s.get("median_comments") or 0
        add(W["audience"] * (0.4 if mc >= 20 else 0.25 if mc >= 5 else 0), "audience: not deep-checked, %d comments on a typical video" % mc)
    if s.get("median_comments") is not None and s["median_comments"] < 3:
        add(-10, "penalty: almost no comments on a typical video")
    g = (rec.get("geo") or {}).get("verdict")
    ag = rec.get("audience_geo") or {}
    if ag.get("estimate") is not None:  # the audience estimate, once the deep check has made one
        share = min(1.0, ag["estimate"] / (ag.get("min_share") or 0.5))
        add(W["geography"] * share, "geography: audience about %d%% in %s (%s confidence)" % (round(100 * ag["estimate"]), "/".join(ag["target"]), ag["confidence"]))
    else:
        add(W["geography"] * {"market": 1.0, "ambiguous": 0.3}.get(g, 0), "geography: %s" % g)
    best, label = 0.0, "no brand history seen"
    for r in rec.get("relationships") or []:
        if r["kind"] == "own":
            continue
        if not r["paid_posts"]:
            v, l = 0.2, "mentions %s unpaid" % r["brand"]
        elif r["kind"] == "direct":
            v = 1.0 if (r["status"] == "lapsed" and r["paid_posts"] >= 4) else 0.8
            v = v / 2 if r["edge"] == "none" else v
            l = "%d sponsored video(s) for direct competitor %s (%s)" % (r["paid_posts"], r["brand"], r["status"])
        else:
            v, l = 0.55, "%d sponsored video(s) for indirect competitor %s" % (r["paid_posts"], r["brand"])
        if r["paid_posts"] >= 4 and not r["bundle"]:
            v = min(1.0, v + 0.2)
            l += ", 4 or more: the brand kept paying"
        if v > best:
            best, label = v, l
    if best < 0.3 and rec.get("sponsored_videos"):
        best, label = 0.3, "%d sponsored video(s) for other brands" % rec["sponsored_videos"]
    add(W["brand_proof"] * best, "brand proof: %s" % label)
    pv = rec.get("paid_vs_organic") or {}
    if pv.get("ratio") is not None and pv["ratio"] < 0.6 and pv["paid_n"] >= 3:
        add(-10, "penalty: sponsored videos get %d%% of the views of the rest" % round(100 * pv["ratio"]))
    lk = rec.get("lookalike")
    if lk:
        add(5 if lk["similarity"] >= 0.5 else 3, "bonus: lookalike of your top creator %s (%.2f)" % (lk["seed"], lk["similarity"]))
    lp = rec.get("link_page") or {}
    if lp.get("links", 0) >= cfg.get("heavy_link_page", 12):
        add(-5, "penalty: link page lists %d links, promotes many products" % lp["links"])
    return int(max(0, min(100, round(pts)))), why


def title_gate(cfg, c, cand, use_state):
    """Free: the channel name and the titles that surfaced it. Returns a final record, or None to continue."""
    text = " ".join(cand["texts"])
    v, why = filters.meta_gate(cfg, cand["channel_id"], text)
    oc = filters.is_own_or_competitor(cfg, cand["name"], cand["name"])
    if v == "reject" or oc:
        return {"handle": cand["channel_id"], "channel_id": cand["channel_id"], "name": cand["name"], "lane": "reject", "reason": oc or why, "lanes": sorted(set(cand["lanes"]))}
    if cand["channel_id"] in cfg.seed_ids:
        return {"handle": cand["channel_id"], "channel_id": cand["channel_id"], "name": cand["name"], "lane": "skip_existing_partner",
                "reason": "one of your imported top creators (a seed)", "lanes": sorted(set(cand["lanes"]))}
    if use_state and store.is_seen(c, cand["channel_id"]):
        return {"handle": cand["channel_id"], "channel_id": cand["channel_id"], "name": cand["name"], "lane": "skip_seen", "reason": "seen %s" % store.is_seen(c, cand["channel_id"])[2][:10],
                "lanes": sorted(set(cand["lanes"]))}
    return None


def judge(cfg, cand, meta, videos, fetch_links=True):
    """Every gate and signal that needs the channel record and its upload history. Pure given its inputs,
    apart from the free link-page fetch, so regate.py can replay it on saved data."""
    cid = cand["channel_id"]
    h = meta.get("handle") or cid
    rec = {"handle": h, "channel_id": cid, "url": platform.profile_url(h), "lanes": sorted(set(cand["lanes"])), "flags": [],
           "name": meta.get("name") or cand["name"], "followers": meta.get("subs"), "bio": meta.get("description") or "", "country": meta.get("country")}
    if cand.get("seed_of"):
        rec["seed_of"] = cand["seed_of"]
        how = "/".join(sorted(set(l for l in cand["lanes"] if l in LATERAL)))
        rec["flags"].append("found next to your top creator%s %s (lateral search: %s)" % ("s" if len(cand["seed_of"]) > 1 else "", ", ".join(cand["seed_of"][:3]), how))
    text, bio, name = " ".join(cand["texts"]), rec["bio"], rec["name"]

    def out(lane, reason):
        rec.update(lane=lane, reason=reason)
        return rec
    band = cfg["band"]
    if rec["followers"] is None:
        rec["flags"].append("subscriber count hidden: band not checked")
    elif not (band["min_followers"] <= rec["followers"] <= band["max_followers"]):
        return out("reject", "band:%s" % rec["followers"])
    if rec["country"] and rec["country"] not in cfg["geo"]["markets"] and cfg["geo"]["mode"] == "reject":
        rec["geo"] = {"country": rec["country"], "verdict": "out"}
        return out("reject", "geo_out:%s" % rec["country"])
    oc = filters.is_own_or_competitor(cfg, h, name)
    if oc:
        return out("reject", oc)
    # an about text is long and often mentions a shop or merch: only its opening line says what the channel is
    corp = filters.looks_corporate(cfg, name, h, bio[:160])
    if corp:
        return out("reject", corp)
    link = bio_link(bio)
    rec["bio_link"] = link
    bio_page = None
    if link and fetch_links:
        pace()
        bio_page = call(link, raw=True, timeout=20)
        rec["link_page"] = filters.link_page_stats(bio_page[1] or "")
    org = filters.looks_organisation(cfg, bio, (rec.get("link_page") or {}).get("titles"), None)
    if org:
        return out("reject", org)
    # ---- upload history ----
    longs = [v for v in videos if not v.get("is_short")]
    shorts = [v for v in videos if v.get("is_short")]
    rec["longform_count"], rec["shorts_count"] = len(longs), len(shorts)
    # Which format the channel is judged on. `format_focus` in the brand config:
    #   longform_first (default)  long-form when there is enough of it, otherwise Shorts, flagged
    #   longform                  long-form only: a Shorts-led channel is rejected
    #   shorts                    Shorts only: a channel without enough Shorts is rejected
    focus = cfg.get("format_focus", "longform_first")
    enough_long, enough_short = len(longs) >= cfg.get("min_longform", 3), len(shorts) >= cfg.get("min_shorts", 5)
    lv = sorted(v["views"] for v in longs if v.get("views") is not None)
    rec["median_views_longform"] = lv[len(lv) // 2] if lv else None
    if focus == "shorts":
        if not enough_short:
            return out("reject", "few_shorts:%d Shorts in the last %d uploads" % (len(shorts), len(videos)))
        rec["format"] = "shorts"
    elif enough_long:
        rec["format"] = "long-form"
    elif focus == "longform":
        return out("reject", "shorts_led:%d long-form videos in the last %d uploads" % (len(longs), len(videos)))
    elif enough_short:
        rec["format"] = "shorts"
        rec["flags"].append("Shorts-led channel: %d of the last %d uploads are Shorts, so views, niche share and sponsorships are read from Shorts" % (len(shorts), len(videos)))
    else:
        return out("reject", "few_videos:%d long-form and %d Shorts in the last %d uploads" % (len(longs), len(shorts), len(videos)))
    if rec["format"] == "shorts":
        longs = shorts  # from here on "longs" is the format the channel is judged on
    stats = filters.post_stats(cfg, longs, rec["followers"])
    if stats is None:
        return out("review_unverified", "no_dated_videos")
    er = sorted(((v.get("likes") or 0) + (v.get("comments") or 0)) / v["views"] for v in longs if v.get("views"))
    stats["engagement_rate"] = round(er[len(er) // 2], 4) if er else None  # per view on YouTube, not per subscriber
    sv = sorted(v["views"] for v in shorts if v.get("views") is not None)
    stats["median_views_shorts"] = sv[len(sv) // 2] if sv else None
    rec["stats"] = stats
    if stats["days_since_last"] > cfg["dormancy_days"]:
        return out("reject", "dormant:%dd" % stats["days_since_last"])
    if stats["median_views_organic"] is not None and stats["median_views_organic"] < cfg["min_median_views"]:
        return out("reject", "low_views:%d" % stats["median_views_organic"])
    titles = [v["caption"] for v in longs]
    bucket, bwhy = filters.classify_relevance(cfg, " ".join([name, bio, text] + titles))
    rec.update(bucket=bucket, bucket_why=bwhy)
    if bucket in ("off", "neutral"):
        return out("reject", bwhy)
    recent = sorted(longs, key=lambda v: -(v["ts"] or 0))
    rec["domain_share"] = filters.domain_share(cfg, [v["caption"] for v in recent[: cfg["recent_posts"]]])
    rec["domain_share_history"] = filters.domain_share(cfg, titles)
    if rec["domain_share_history"] < cfg.get("min_domain_share", 0):
        return out("reject", "off_domain:%.2f of the last %d long-form titles on the domain" % (rec["domain_share_history"], len(titles)))
    if rec["domain_share"] < cfg.get("flag_domain_share", 0):
        rec["flags"].append("the domain is a side theme: %d%% of recent titles" % round(100 * rec["domain_share"]))
    # ---- geography: the channel's stated country decides when there is one ----
    geo = filters.geo_signal(cfg, [name, bio] + titles[: cfg["recent_posts"]], bio)
    if rec["country"]:
        geo["country"] = rec["country"]
        geo["verdict"] = "market" if rec["country"] in cfg["geo"]["markets"] else "out"
    rec["geo"] = geo
    if geo["verdict"] == "out" and cfg["geo"]["mode"] == "reject":
        return out("reject", "geo_out:%s" % (rec["country"] or "lang=%s out_markers=%d" % (geo["lang"], geo["out_markers"])))
    if geo["verdict"] == "ambiguous":
        rec["flags"].append("geography unconfirmed: no country on the channel and no home-market signal, check before outreach")
    # ---- sponsorship history: descriptions carry it for the whole back catalogue ----
    # A marker in most descriptions is the channel's standing boilerplate (an affiliate line, a merch
    # code), not a sponsorship. Then only an explicit sponsor statement counts.
    loose = [bool(cfg.sponsor_marker.search(v.get("description") or "")) for v in videos]
    boiler = len(videos) >= 5 and sum(loose) / len(videos) >= 0.5
    for v, hit in zip(videos, loose):
        v["paid_flag"] = bool(STRICT_SPONSOR_RX.search(v.get("description") or "")) if boiler else hit
    if boiler:
        rec["flags"].append("the same promo wording is in %d%% of descriptions, so only explicit sponsor statements were counted" % round(100 * sum(loose) / len(videos)))
    rposts = [{"caption": v["caption"] + " " + (v.get("description") or ""), "ts": v.get("ts"), "url": v["url"], "paid_flag": v["paid_flag"]} for v in videos]
    seen_urls = {v["url"] for v in videos}
    rposts += [{"caption": x["caption"], "ts": None, "url": x["url"]} for x in cand["collab_hits"] if x["url"] not in seen_urls]
    rels = filters.relationships(cfg, rposts)
    rec["relationships"] = rels
    own = next((r for r in rels if r["kind"] == "own"), None)
    if own and own["paid_posts"]:
        return out("skip_existing_partner", "sponsored video for %s" % own["brand"])
    if own:
        rec["flags"].append("mentions %s without a sponsor marker: possible customer or reviewer, treat as warm" % own["brand"])
    for r in rels:
        if r["kind"] == "direct" and r["paid_posts"] and r["status"] != "lapsed":
            rec["flags"].append("active with direct competitor %s: check exclusivity" % r["brand"])
    rec["sponsored_videos"] = sum(1 for v in longs if v["paid_flag"])
    names = Counter(m.strip() for v in longs for m in SPONSOR_NAME_RX.findall(v.get("description") or ""))
    if names:
        rec["sponsors"] = [n for n, _ in names.most_common(6)]
    if stats["likely_boosted"]:
        rec["flags"].append("%d recent video(s) are far above the usual views with a low like rate and are left out of the median (estimate)" % len(stats["likely_boosted"]))
    paid_posts = [dict(v, caption="") for v in longs]  # sponsorship is read from descriptions, never guessed from titles
    rec["promo_share"] = round(sum(1 for v in longs if v["paid_flag"]) / len(longs), 2)
    pv = filters.paid_vs_organic(cfg, paid_posts)
    rec["paid_vs_organic"] = pv
    if pv["ratio"] is not None and pv["ratio"] < 0.6:
        rec["flags"].append("sponsored videos get %d%% of the views of the rest (%d sponsored videos seen): the audience tunes out sponsored content" % (round(100 * pv["ratio"]), pv["paid_n"]))
    rec["notable_posts"] = filters.notable_posts(cfg, paid_posts, stats)
    if rec.get("link_page"):
        titles_lp = " | ".join(rec["link_page"].get("titles") or [])
        for b in cfg.brands:
            if b["rx"] and b["rx"].search(titles_lp) and b["kind"] == "own":
                return out("skip_existing_partner", "live link or code for %s on the link page" % b["name"])
            if b["rx"] and b["rx"].search(titles_lp):
                rec["flags"].append("link page carries a live link or code for %s (%s competitor): check exclusivity" % (b["name"], b["kind"]))
        if rec["link_page"]["links"] >= cfg.get("heavy_link_page", 12):
            rec["flags"].append("link page lists %d links: promotes many products, so the audience may be saturated and rates may be high" % rec["link_page"]["links"])
    # ---- email ladder: the about text and the creator's own recent descriptions, then the link page ----
    own_text = bio + "\n" + "\n".join((v.get("description") or "")[:1500] for v in recent[:5])
    best, found, tried = emails.ladder(dict(cand, handle=h), {"name": name, "bio": own_text, "bio_link": link}, bio_page=bio_page)
    rec.update(email=best["email"] if best else None, email_meta=best, emails_found=found, email_steps=tried)
    rec["entry_posts"] = pick_entry_posts(cfg, dict(cand, _format=rec["format"]), videos, rels)
    rec["recent_videos"] = [{"url": v["url"], "caption": v["caption"][:160], "views": v.get("views"), "likes": v.get("likes"), "comments": v.get("comments"), "ts": v.get("ts"),
                             "is_short": v.get("is_short"), "paid": v["paid_flag"]} for v in videos]
    rec["bio"] = bio[:600]
    profs = getattr(cfg, "seed_profiles", None)
    if profs:  # creator dimension: how close is this channel to one of the operator's top creators
        sim, seed, shared = seeds.best_lookalike(profs, meta, videos)
        if seed and sim >= seeds.settings(cfg)["lookalike_min"]:
            rec["lookalike"] = {"seed": seed, "similarity": sim, "shared": shared}
            rec["flags"].append("lookalike of your top creator %s: similarity %.2f (shared: %s)" % (seed, sim, ", ".join(shared) or "size, country, format"))
    rec["score"], rec["score_why"] = score(cfg, rec)
    return out("review" if cfg["hold_auto"] else "auto", "passed all gates")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--brand", required=True)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--no-state", action="store_true")
    ap.add_argument("--out")
    a = ap.parse_args()
    cfg = filters.Cfg(os.path.join(ROOT, "config", "%s.yml" % a.brand))
    cfg.seed_ids = seeds.ids(a.brand)
    cfg.seed_profiles = seeds.profiles_for(a.brand)
    queries = plan_queries(cfg)
    use_state = not a.no_state
    c = store.conn(a.brand) if use_state else None
    relevant = lambda t: filters.classify_relevance(cfg, t)[0] in ("core", "domain")
    sq, seeds_used, seed_status = seeds.plan(cfg, a.brand, c, cfg.get("max_searches", 14), yt.rss, relevant)
    if sq:  # seed searches take their share of the budget; the moment and competitor searches keep the rest
        queries = queries[: max(0, cfg.get("max_searches", 14) - len(sq))] + sq
    log("seeds: %s" % seed_status)
    if a.dry_run:
        n = Counter(l for l, _, _ in queries)
        log("query plan: %s" % dict(n))
        for lane, q, _ in queries:
            log("  %-17s %s" % (lane, q))
        qd = yt.quota_today()
        api_search = cfg.get("search_backend", "keyless") == "api"
        log("backend: %s | search: %s | a run may use %d quota units | today %d of %d used, %d of %d runs" % (
            "YouTube Data API" if yt.API_KEY else "keyless (no YOUTUBE_API_KEY)", "API, %d units" % (100 * len(queries)) if api_search else "keyless, no quota",
            yt.RUN_CAP, qd["units"], qd["daily_cap"], qd["runs"], qd["max_api_runs"]))
        return
    out_dir = a.out or os.path.join(ROOT, "out", a.brand, str(date.today()))
    ledger.start_run(cfg.get("caps") or {}, os.environ.get("RUN_TAG"))
    log("== api: %s" % yt.start_run())
    n_prof = seeds.refresh_profiles(a.brand, yt)
    if n_prof:
        cfg.seed_profiles = seeds.profiles_for(a.brand)
        log("seed profiles refreshed: %d" % n_prof)
    log("== discover")
    cands, qlog = discover(cfg, c, queries, use_state)
    peer_rows, peers_used = seeds.peers(cfg, a.brand, yt, c)
    for r in peer_rows:  # creator dimension: peer creators who comment on a seed's top video
        d = cands.setdefault(r["channel_id"], {"channel_id": r["channel_id"], "name": r["channel"], "lanes": [], "entry_posts": [], "texts": [],
                                               "snippet_emails": [], "collab_hits": []})
        d["lanes"].append("lookalike")
        d["texts"].append(r["channel"])
        if r["seed"] not in d.setdefault("seed_of", []):
            d["seed_of"].append(r["seed"])
    if peer_rows:
        log("  lookalike         %2d peer creators commenting on your top creators' videos" % len(peer_rows))
    seeds.mark_walked(c, seeds_used + peers_used)
    store.dump_json({"candidates": cands, "queries": qlog}, os.path.join(out_dir, "discovery.json"))
    log("candidates: %d unique channels" % len(cands))
    # lateral finds first: they sit next to what already worked and pass far more often than cold searches
    order = sorted(cands.values(), key=lambda d: -(2 * len(set(d["lanes"])) + len(d["entry_posts"]) + (3 if set(d["lanes"]) & set(LATERAL) else 0)))
    log("== gates")
    results, enrich, st = [], {}, {"channels": 0, "channel_fail": 0, "history_fail": 0}
    for i, cand in enumerate(order, 1):
        rec = title_gate(cfg, c, cand, use_state)
        if rec is None and st["channels"] >= cfg["max_profiles"]:
            rec = {"handle": cand["channel_id"], "channel_id": cand["channel_id"], "name": cand["name"], "lane": "not_checked", "reason": "channel_budget", "lanes": sorted(set(cand["lanes"]))}
        if rec is None:
            st["channels"] += 1
            meta = yt.channel_record(cand["channel_id"])
            if meta.get("error"):
                st["channel_fail"] += 1
                rec = {"handle": cand["channel_id"], "channel_id": cand["channel_id"], "name": cand["name"], "lane": "review_unverified", "reason": "channel_unreadable", "lanes": sorted(set(cand["lanes"]))}
            else:
                band, subs = cfg["band"], meta.get("subs")
                videos = []
                out_of_market = meta.get("country") and meta["country"] not in cfg["geo"]["markets"] and cfg["geo"]["mode"] == "reject"
                if (subs is None or band["min_followers"] <= subs <= band["max_followers"]) and not out_of_market:  # history only where it can matter
                    up = yt.uploads(cand["channel_id"], cfg.get("history_posts", 50))
                    videos = up["videos"]
                    if not videos:
                        st["history_fail"] += 1
                enrich[cand["channel_id"]] = {"meta": meta, "videos": videos}
                try:
                    rec = judge(cfg, cand, meta, copy.deepcopy(videos))
                except Exception as e:  # one bad channel never kills a run
                    rec = {"handle": cand["channel_id"], "channel_id": cand["channel_id"], "name": cand["name"], "lane": "error", "reason": str(e)[:160], "lanes": sorted(set(cand["lanes"]))}
                if use_state and rec["lane"] in ("review", "auto"):
                    store.snapshot(c, cand["channel_id"], [v for v in videos if v.get("id")])
        results.append(rec)
        if use_state and rec["lane"] not in ("not_checked", "error", "skip_seen", "review_unverified"):
            store.mark_seen(c, rec["channel_id"], rec["lane"], rec["reason"])
        if rec["lane"] in ("review", "auto"):
            log("  [%3d/%d] PASS %-28s subs=%-7s views=%-7s %s email=%s score=%s" % (i, len(order), rec["handle"][:28], rec.get("followers"),
                (rec.get("stats") or {}).get("median_views_organic"), rec.get("bucket"), "yes" if rec.get("email") else "no", rec.get("score")))
        elif i % 25 == 0:
            log("  [%3d/%d] ... channels read %d, api units this run %d" % (i, len(order), st["channels"], yt.API_UNITS[0]))
    store.dump_json(enrich, os.path.join(out_dir, "enrichment.json"))  # lets regate.py replay the gates for free
    if use_state:
        c.commit()
    lanes = Counter(r["lane"] for r in results)
    reasons = Counter(r["reason"].split(":")[0] for r in results if r["lane"] == "reject")
    passed = [r for r in results if r["lane"] in ("review", "auto")]
    digest = {
        "brand": a.brand, "date": str(date.today()), "queries": qlog, "candidates": len(cands), "lanes": dict(lanes),
        "reject_reasons": dict(reasons.most_common()), "passed": len(passed), "with_email": sum(1 for r in passed if r.get("email")),
        "email_steps": dict(Counter(r["email_meta"]["step"] for r in passed if r.get("email_meta"))),
        "seeds": seed_status, "keyless": st, "backend": yt.backend(), "api_units": yt.API_UNITS[0], "quota": yt.quota_today(), "ledger": ledger.summary(),
    }
    store.dump_json({"digest": digest, "results": results}, os.path.join(out_dir, "results.json"))
    log("== digest")
    log("lanes:", dict(lanes))
    log("reject reasons:", dict(reasons.most_common()))
    log("passed %d | with email %d %s" % (len(passed), digest["with_email"], digest["email_steps"]))
    log("channels: %s | backend %s, %d api units this phase" % (st, yt.backend(), yt.API_UNITS[0]))
    log("-> %s" % os.path.join(out_dir, "results.json"))


if __name__ == "__main__":
    sys.exit(main())
