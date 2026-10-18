"""Deep check: comments, the accounts behind them, the audience score, and transcripts.

  python phase2.py --brand <slug> [--date YYYY-MM-DD]

Runs on channels that passed every gate, best score first. With a YouTube Data API key this costs
about 3 quota units per channel: one comment page of up to 100 threads with author ids and creator
replies, and one call that looks up 50 commenter accounts at once. The audience-geography estimate
adds about 5 more: two more comment pages and the countries on up to 150 commenters' channels. Without a key it reads the top
40 comments keyless and skips the commenter lookup. Transcripts come from the video's captions and
cost nothing.
"""
import argparse
import json
import os
import sys
import time
from collections import Counter
from datetime import date

import phase1
from engine import audience_geo, comments, filters, ledger, platform, store
from engine.providers import yt

ROOT = os.path.dirname(os.path.abspath(__file__))


def log(*a):
    print(*a, flush=True)


def pick_video(rec):
    """The entry video when it is this channel's own long-form upload, otherwise the most-commented recent one."""
    want_short = rec.get("format") == "shorts"
    vids = {v["url"]: v for v in rec.get("recent_videos") or [] if bool(v.get("is_short")) == want_short}
    for p in rec.get("entry_posts") or []:
        v = vids.get(p["url"])
        if v and (v.get("comments") or 0) >= 5:
            return p["url"], v["comments"]
    if vids and all(v.get("comments") is None for v in vids.values()):
        # keyless: the RSS feed has no comment counts, so take the entry video or the most-viewed recent one
        for p in rec.get("entry_posts") or []:
            if p["url"] in vids:
                return p["url"], None
        best = max(vids.values(), key=lambda v: v.get("views") or 0)
        return best["url"], None
    best = max(vids.values(), key=lambda v: v.get("comments") or 0, default=None)
    if best and (best.get("comments") or 0) >= 3:
        return best["url"], best["comments"]
    return None, (best or {}).get("comments")


def commenter_summary(rows):
    """Who is commenting: account age and activity for up to 50 commenters, in one API unit.
    Most real YouTube viewers have no uploads, so the signal is account age, not activity."""
    brief = yt.channels_brief([r.get("author_id") for r in rows])
    now, out = time.time(), []
    for cid, b in brief.items():
        age = (now - b["created"]) / 86400.0 if b["created"] else None
        out.append({"subs": b["subs"], "videos": b["videos"], "age_days": round(age) if age is not None else None, "thin": age is not None and age < 60})
    n = len(out) or 1
    return out, {"profiled": len(out), "thin": sum(1 for c in out if c["thin"]), "with_videos": sum(1 for c in out if c["videos"]),
                 "languages": {}, "established_share": round(sum(1 for c in out if not c["thin"]) / n, 2) if out else 0.5,
                 "median_age_days": sorted(c["age_days"] or 0 for c in out)[len(out) // 2] if out else None}


def audience_geography(cfg, rec, first_rows, first_published, source):
    """The free audience-geography estimate (engine/audience_geo.py): the comment-check video plus a couple
    more recent videos (1 unit each), and the countries on up to 150 commenters' channels (1 unit per 50)."""
    def fresh(row, pub):  # the first 12 hours after upload say when the video went up, not where viewers live
        ts = audience_geo.parse_ts(row.get("ts") or "")
        return ts if ts and not (pub and ts.timestamp() - pub < 12 * 3600) else None

    pub0 = audience_geo.parse_ts(first_published or "")
    pub0 = pub0.timestamp() if pub0 else None
    sample = [{"text": r["text"], "ts": fresh(r, pub0), "author_id": r.get("author_id")} for r in first_rows]
    if source == "api":
        want_short = rec.get("format") == "shorts"
        now = time.time()
        used = {(rec.get("audience") or {}).get("video")}
        extra = sorted([v for v in rec.get("recent_videos") or [] if v["url"] not in used and bool(v.get("is_short")) == want_short
                        and v.get("ts") and now - v["ts"] > 3 * 86400 and (v.get("comments") or 0) >= 10],
                       key=lambda v: -(v.get("comments") or 0))[: max(0, int((cfg.get("geo") or {}).get("audience_videos", 3)) - 1)]
        for v in extra:
            for r in yt.comment_sample(platform.post_id(v["url"]), 100):
                sample.append({"text": r["text"], "ts": fresh(r, v["ts"]), "author_id": r.get("author_id")})
    countries = yt.commenter_countries([c["author_id"] for c in sample]) if source == "api" else {}
    titles = [v.get("caption") or "" for v in rec.get("recent_videos") or []]
    meta = {"country": rec.get("country")}
    return audience_geo.estimate(cfg, sample, countries or audience_geo.Counter(), meta, titles, rec.get("bio") or "", source)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--brand", required=True)
    ap.add_argument("--date", default=str(date.today()))
    a = ap.parse_args()
    cfg = filters.Cfg(os.path.join(ROOT, "config", "%s.yml" % a.brand))
    path = os.path.join(ROOT, "out", a.brand, a.date, "results.json")
    data = json.load(open(path))
    ledger.start_run(cfg.get("caps") or {}, os.environ.get("RUN_TAG"))
    log("== api: %s" % yt.join_run())
    passed = sorted([r for r in data["results"] if r["lane"] in ("review", "auto")], key=lambda r: -r.get("score", 0))
    log("== deep: %d passed, checking up to %d" % (len(passed), cfg["max_deep"]))
    done = 0
    for i, rec in enumerate(passed):
        if i >= cfg["max_deep"]:
            rec["deep"] = "not reached: max_deep"
            continue
        ep = (rec.get("entry_posts") or [None])[0]
        if ep and i < cfg.get("transcripts_top", 8) and not ep.get("transcript"):
            t = yt.transcript(platform.post_id(ep["url"]), tuple(cfg["geo"]["market_langs"]))
            ep["transcript"] = t[:2500] if t else None
        if rec.get("audience"):  # already checked in an earlier pass of this run
            done += 1
            continue
        url, n = pick_video(rec)
        if not url:
            rec["deep"] = "skipped: too few comments to sample (max %s on a recent video)" % n
            rec["flags"].append("almost no comments on recent videos")
            continue
        r = yt.comment_threads(platform.post_id(url), cfg.get("comments_per_post", 100))
        if r["error"] or not r["rows"]:
            rec["deep"] = "comments unreadable: %s" % (r["error"] or "none returned")
            continue
        sample, summary = commenter_summary(r["rows"]) if r["source"] == "api" else ([], {"profiled": 0, "thin": 0, "with_videos": 0, "languages": {}, "established_share": 0.5})
        aud = comments.score(cfg, r["rows"], summary, cfg.domain)
        aud.update(video=url, sample_comments=[c["text"][:160] for c in r["rows"][:8]], commenter_sample=sample, source=r["source"])
        rec["audience"] = aud
        if summary["profiled"] and summary["thin"] / summary["profiled"] >= 0.3:
            rec["flags"].append("%d of %d commenters sampled have accounts under 60 days old" % (summary["thin"], summary["profiled"]))
        if aud["out_markers"] > aud["home_markers"] + 2:
            rec["flags"].append("comments carry more out-of-market than home-market markers (%d against %d)" % (aud["out_markers"], aud["home_markers"]))
        geo = audience_geography(cfg, rec, r["rows"], r.get("published"), r["source"])
        rec["audience_geo"] = geo
        if geo.get("verdict") == "misses":
            if geo["action"] == "reject" and geo["confidence"] in ("medium", "high"):
                rec.update(lane="reject", reason="audience_geo: about %d%% in %s" % (round(100 * geo["estimate"]), "/".join(geo["target"])))
            rec["flags"].append("audience geography misses the target: about %d%% in %s (%s confidence)" % (
                round(100 * geo["estimate"]), "/".join(geo["target"]), geo["confidence"]))
        elif geo.get("verdict") == "unclear" or geo.get("estimate") is None:
            rec["flags"].append("audience geography unclear: ask for a YouTube Studio audience screenshot")
        if (geo.get("city") or {}).get("signal") == "none":
            rec["flags"].append("no sign of %s in comments, titles or about text" % geo["city"]["city"])
        rec["deep"] = "done"
        done += 1
        rec["score"], rec["score_why"] = phase1.score(cfg, rec)
        log("  %-28s audience %3d | %3d comments, substantive %.2f, creator replied to %d | commenters %d, %d new accounts | %s" % (
            rec["handle"][:28], aud["score"], aud["texture"]["n"], aud["texture"]["substantive_share"], aud["texture"]["creator_liked"],
            summary["profiled"], summary["thin"], aud["comment_langs"]))
        log("  %-28s audience geo: %s" % ("", "about %d%% in %s, %s confidence (%s)" % (round(100 * geo["estimate"]), "/".join(geo["target"]), geo["confidence"], geo["verdict"])
                                         if geo.get("estimate") is not None else "not enough signal"))
    data["digest"]["deep"] = {"checked": done, "stopped_on_cap": False, "ledger": ledger.summary(), "backend": yt.backend(), "quota": yt.quota_today()}
    store.dump_json(data, path)
    q = yt.quota_today()
    log("deep checked %d | youtube quota today %d of %d units, run %s" % (done, q["units"], q["daily_cap"], (q.get("run_units") or {})))


if __name__ == "__main__":
    sys.exit(main())
