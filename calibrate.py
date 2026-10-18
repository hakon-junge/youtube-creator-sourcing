"""Build the calibration page for a run: what the engine decided, why, and a place to correct it.

  python calibrate.py --brand <slug> [--date YYYY-MM-DD] [--rejections 10]

Shown: every creator that reached vetting (advance, review, hold, vetting reject) and at most
`--rejections` creators the gates rejected, spread across the reject reasons so each gate gets
looked at. About 20 minutes of review. Email addresses are left out of the page on purpose.

The page is self-contained HTML. Published as a Claude artifact with the `db` capability it saves
feedback itself; opened as a local file it offers a "Copy my feedback" button instead.
"""
import argparse
import json
import os
import re
from datetime import date

ROOT = os.path.dirname(os.path.abspath(__file__))
EMAIL_RX = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,}")
REASONS = {
    "low_views": "Organic median under the view floor", "band": "Outside the follower band", "band_hint": "Outside the follower band",
    "dormant": "No recent post", "competitor_account": "Competitor's own account", "own_brand": "The brand's own account",
    "account_missing": "Account not found", "private_account": "Private account", "corporate_marker": "Brand, business or charity account",
    "corporate_name": "Brand, business or charity account", "geo_out": "Outside the market", "off_domain": "Not a domain account",
    "off_hard": "Off-topic content", "business_category": "Brand, business or charity account", "organisation_marker": "Brand, business or charity account", "few_videos": "Too few videos to judge", "shorts_led": "Shorts-led channel (long-form focus)", "few_shorts": "Too few Shorts (Shorts focus)", "off_soft": "Off-topic content", "no domain signal": "No domain signal", "existing_partner": "Existing partner",
    "promotion_account": "Promotion or ad account", "passed free gates": "Passed the free gates", "passed all gates": "Passed all gates",
}
GROUP = {"advance": "advance", "human-review": "review", "hold": "hold", "reject": "vet_reject"}


def label(reason):
    key = (reason or "").split(":")[0]
    return "Existing partner (public paid post)" if key.startswith("public paid post") else REASONS.get(key, key.replace("_", " "))


def record(r, v, group):
    s = r.get("stats") or {}
    h = r.get("handle") or r["channel_id"]
    rec = {"h": h, "url": r.get("url") or "https://www.youtube.com/channel/%s" % (r.get("channel_id") or h), "group": group, "lane": r["lane"].replace("_", " "), "reason": r["reason"],
           "reason_label": label(r["reason"]), "lanes": r.get("lanes") or [], "name": r.get("name"), "followers": r.get("followers"), "cid": r.get("channel_id"),
           "med": s.get("median_views_organic"), "max": s.get("max_views"), "nposts": s.get("n"), "er": s.get("engagement_rate"),
           "ppw": s.get("posts_per_week"), "dsl": s.get("days_since_last"), "ds": r.get("domain_share"), "dsh": r.get("domain_share_history"),
           "geo": (r.get("geo") or {}).get("verdict"), "bio": EMAIL_RX.sub("[email]", (r.get("bio") or "").replace("\n", " / "))[:260] or None,
           "email_step": (r.get("email_meta") or {}).get("step"), "format": r.get("format"), "score": r.get("score"), "score_why": r.get("score_why") or [], "flags": r.get("flags") or []}
    rec["rels"] = ["%s (%s%s): %d posts seen, %d with a paid marker, %s, %s" % (x["brand"], x["kind"], "" if x["kind"] == "own" else " competitor", x["posts"], x["paid_posts"],
                   x["strength"].replace("_", " "), x["status"]) for x in r.get("relationships") or []]
    if r.get("sponsored_videos"):
        rec["rels"].append("%d of the last %d long-form videos carry a sponsor marker%s" % (r["sponsored_videos"], r.get("longform_count") or 0, " (named: %s)" % ", ".join(r["sponsors"]) if r.get("sponsors") else ""))
    rec["notable"] = [{"url": x["url"], "label": "%s, %s" % (x["why"], "%s views" % format(x["views"], ",") if x.get("views") else "%s likes" % format(x.get("likes") or 0, ","))} for x in r.get("notable_posts") or []]
    au = r.get("audience")
    if au:
        t, c = au["texture"], au["commenters"]
        rec["aud"] = {"score": au["score"], "samples": [x.replace("\n", " ") for x in au["sample_comments"][:4]],
                      "summary": "%d comments read: %d questions, %d specific, %d short, %d generic, %d emoji-only; creator replied to %d. %d commenter accounts checked, %d under 60 days old." % (
                          t["n"], t["question"], t["specific"], t["short"], t["generic"], t["emoji"], t["creator_liked"], c["profiled"], c["thin"])}
    if v:
        rec.update(verdict=v["verdict"], why=v["why"], vflags=v["flags"], geo_note=v["geo"], draft=v["draft"], send_via=v["send_via"])
        rec["entry"] = [{"url": e.split(" - ")[0], "label": e.split(" - ", 1)[1] if " - " in e else "Open post"} for e in v.get("entry") or []]
    else:
        rec["entry"] = [{"url": p["url"], "caption": (p.get("caption") or "").replace("\n", " ")[:140]} for p in (r.get("entry_posts") or [])[:2]]
    return {k: x for k, x in rec.items() if x not in (None, [], "")}


def sample_rejections(rejects, n):
    """Round-robin across reject reasons, the creators that got furthest first, so every gate is represented."""
    by = {}
    for r in rejects:
        by.setdefault(r["reason_label"], []).append(r)
    for rows in by.values():
        rows.sort(key=lambda r: (-(1 if r.get("med") is not None else 0), -(r.get("followers") or 0)))
    picked, order = [], sorted(by, key=lambda k: -len(by[k]))
    while len(picked) < n and any(by.values()):
        for k in order:
            if by[k] and len(picked) < n:
                picked.append(by[k].pop(0))
    return picked


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--brand", required=True)
    ap.add_argument("--date", default=str(date.today()))
    ap.add_argument("--rejections", type=int, default=10)
    ap.add_argument("--company")
    a = ap.parse_args()
    d = os.path.join(ROOT, "out", a.brand, a.date)
    res = json.load(open(os.path.join(d, "results.json")))["results"]
    s5p = os.path.join(d, "stage5.json")
    s5 = {c["handle"]: c for c in json.load(open(s5p))["creators"]} if os.path.exists(s5p) else {}
    kept, rejects, partners = [], [], 0
    for r in res:
        v = s5.get(r["handle"])
        if r["lane"] in ("review", "auto"):
            kept.append(record(r, v, GROUP[v["verdict"]] if v else "review"))
        elif r["lane"] == "skip_existing_partner":
            partners += 1
        elif r["lane"] == "reject":
            rejects.append(record(r, None, "engine_reject"))
    shown = sample_rejections(rejects, a.rejections)
    order = {"advance": 0, "review": 1, "hold": 2, "vet_reject": 3, "engine_reject": 4}
    out = sorted(kept + shown, key=lambda r: (order[r["group"]], -(r.get("score") or 0), r["h"]))
    n = lambda g: sum(1 for r in out if r["group"] == g)
    company = a.company or a.brand
    data = {"run": "%s-%s" % (a.brand, a.date), "company": company, "date": a.date, "creators": out,
            "hidden_rejections": len(rejects) - len(shown), "funnel": [
                {"n": len(res), "label": "creators found"}, {"n": len(rejects), "label": "rejected by the gates"},
                {"n": partners, "label": "existing partners skipped"}, {"n": len(kept), "label": "reached vetting"},
                {"n": n("advance"), "label": "advance"}, {"n": sum(1 for r in out if r.get("draft")), "label": "drafts written"}]}
    tpl = open(os.path.join(ROOT, "calibration", "template.html")).read()
    if os.path.exists(os.path.join(ROOT, "brand", a.brand, "REHEARSAL")):
        company += " (rehearsal: made-up inputs)"
    page = tpl.replace("__COMPANY__", company).replace("__DATA__", json.dumps(data, ensure_ascii=False).replace("</", "<\\/"))
    dest = os.path.join(ROOT, "calibration", "%s-%s.html" % (a.brand, a.date))
    open(dest, "w").write(page)
    print("calibration page: %s | %d vetted + %d of %d rejections shown | emails in page: %d" % (
        dest, len(kept), len(shown), len(rejects), len(EMAIL_RX.findall(json.dumps(data)))))


if __name__ == "__main__":
    main()
