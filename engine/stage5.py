"""Stage 5 writer: vetting note + first-touch draft per creator into the local CRM. Nothing is sent.

The verdicts, observations and flags come from the vetting pass (the per-brand builder file);
the facts come from handoff.json. The draft follows the first-approach structure of the voice skill.
"""
import csv
import json
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def scrub(text):
    """Voice gate: no em dashes, no exclamation marks, never 'honest'."""
    t = text.replace("—", " - ").replace("–", "-")
    t = re.sub(r"\bhonestly\b", "genuinely", t, flags=re.I)
    t = re.sub(r"\bhonest\b", "straight", t, flags=re.I)
    return t.replace("!", ".")


def draft_email(L, pain, c):
    hi = L["hi"].format(n=c["first"]) if c.get("first") else L["hi_anon"]
    p1, p2 = pain[c["pain"]]
    body = [hi, L["intro"], c["obs"], L["bridge"] + " " + L["vp"], p1 + " " + p2, L["why"].format(c=c["cfit"]), L["rate"]]
    if c.get("ask_exclusivity"):
        body.append(L["exclusivity"].format(b=c["ask_exclusivity"]))
    body += [L["close"], L["ps"]]
    return scrub("\n\n".join(body))


def draft_dm(L, c):
    hi = L["hi"].format(n=c["first"]) if c.get("first") else L["hi_anon"]
    parts = [hi, L["intro"], c["obs"], L["dm_ask"].format(c=c["cfit"])]
    if c.get("ask_exclusivity"):  # asking outright is the respectful move when they already work with a competitor
        parts.append(L["exclusivity"].format(b=c["ask_exclusivity"]))
    return scrub(" ".join(parts + [L["dm_close"]]))


def note(brand, r, c, L, pain, run_date):
    s, a = r.get("stats") or {}, r.get("audience")
    M = ["# @%s - %s" % (r["handle"], c["verdict"].upper()), "",
         "Brand: %s | Platform: YouTube | Run: %s | Engine score: %s" % (brand, run_date, r.get("score")), "",
         "## Vetting note", "",
         "- **Verdict:** %s" % c["verdict"], "- **Why:** %s" % c["why"],
         "- **Niche / persona:** %s / %s" % (c.get("niche", "-"), c.get("persona", "-")),
         "- **Channel:** %s | %s subscribers | found via %s" % (r["url"], r.get("followers"), ", ".join(r["lanes"])),
         "- **Format judged:** %s (long-form median %s, Shorts median %s)" % (r.get("format"), r.get("median_views_longform"), s.get("median_views_shorts")),
         "- **Views:** judged-format median %s over %s videos (max %s) | shorts median %s | median comments %s | engagement %s per view | %s long-form a week | last upload %s days ago" % (
             s.get("median_views_organic"), s.get("n"), s.get("max_views"), s.get("median_views_shorts"), s.get("median_comments"), s.get("engagement_rate"), s.get("posts_per_week"), s.get("days_since_last")),
         "- **Sponsorships:** %s of the last %s long-form videos carry a sponsor marker%s" % (r.get("sponsored_videos"), r.get("longform_count"), " (sponsors named: %s)" % ", ".join(r["sponsors"]) if r.get("sponsors") else ""),
         "- **Domain share:** %d%% of the last 10 long-form titles, %d%% of all read" % (round(100 * r.get("domain_share", 0)), round(100 * r.get("domain_share_history", 0))),
         "- **Geography:** %s" % c["geo"],
         "- **Contact:** %s" % ("%s (%s, read from %s: %s)" % (r["email"], r["email_meta"]["type"], r["email_meta"]["step"], r["email_meta"]["source"]) if r.get("email") else "no public email found - use the channel's contact options or another platform")]
    for rel in r.get("relationships") or []:
        if rel["kind"] == "own":
            M.append("- **Brand history:** mentions %s in %d post(s), %d with a paid marker" % (rel["brand"], rel["posts"], rel["paid_posts"]))
        else:
            M.append("- **Brand history:** %s (%s competitor) - %d posts seen, %d with a paid marker, %s, %s" % (
                rel["brand"], rel["kind"], rel["posts"], rel["paid_posts"], rel["strength"].replace("_", " "), rel["status"]))
    if a:
        t, cm = a["texture"], a["commenters"]
        M.append("- **Audience check** (%s): %d comments read - %d questions, %d specific, %d short, %d generic, %d emoji-only; creator replied to %d. %d commenters profiled, %d thin. Engine audience score %d (uncalibrated)." % (
            a["video"], t["n"], t["question"], t["specific"], t["short"], t["generic"], t["emoji"], t["creator_liked"], cm["profiled"], cm["thin"], a["score"]))
    else:
        M.append("- **Audience check:** %s" % r.get("deep", "not run"))
    if r.get("audience_geo"):
        M.append("- **Audience geography:** %s" % re.sub(r"^Audience geography(: | \(estimate, (\w+) confidence\): )", lambda m: "estimate, %s confidence: " % m.group(2) if m.group(2) else "", r["audience_geo"]["summary"]))
    for f in c.get("flags") or []:
        M.append("- **FLAG:** %s" % f)
    for f in r.get("flags") or []:
        M.append("- **Engine flag:** %s" % f)
    M += ["", "## Entry posts", ""]
    for p in c.get("entry") or []:
        M.append("- %s" % p)
    if r.get("notable_posts"):
        M += ["", "## Posts worth opening before deciding", ""]
        for x in r["notable_posts"]:
            M.append("- %s - %s, %s" % (x["url"], x["why"], "%s views" % format(x["views"], ",") if x.get("views") else "%s likes" % format(x.get("likes") or 0, ",")))
    pv = r.get("paid_vs_organic") or {}
    if pv.get("ratio") is not None:
        M += ["", "Promotional posts: %d seen, median %s %s against %s for organic posts (%d%%)." % (pv["paid_n"], format(pv["paid_median"], ","), pv["measure"], format(pv["organic_median"], ","), round(100 * pv["ratio"]))]
    if c["verdict"] in ("reject", "hold"):
        M += ["", "_No draft: %s._" % ("rejected" if c["verdict"] == "reject" else "held until the open checks above are done")]
        return "\n".join(M) + "\n", None
    M += ["", "## OUTREACH DRAFT - NOT SENT", ""]
    if r.get("email"):
        text = draft_email(L, pain, c)
        M += ["Send via: email to %s" % r["email"], "Subject: %s" % L["subj"].format(h="@" + r["handle"]), "Unfilled: %s" % L["unfilled"], "", text]
    else:
        text = draft_dm(L, c)
        M += ["Send via: no public email found - short message for a contact form or another platform", "Unfilled: %s" % L["unfilled"], "", text]
    return "\n".join(M) + "\n", text


def write_all(brand, run_date, L, pain, creators):
    hand = {r["handle"]: r for r in json.load(open(os.path.join(ROOT, "out", brand, run_date, "handoff.json")))["handoff"]}
    d = os.path.join(ROOT, "crm", brand)
    os.makedirs(os.path.join(d, "notes"), exist_ok=True)
    rows, out = [], []
    skipped = [c["handle"] for c in creators if c["handle"] not in hand]
    for c in creators:
        if c["handle"] not in hand:  # the gates no longer pass this creator
            continue
        r = hand[c["handle"]]
        md, text = note(brand, r, c, L, pain, run_date)
        open(os.path.join(d, "notes", "%s.md" % c["handle"]), "w").write(md)
        rows.append({"handle": c["handle"], "profile_url": r["url"], "platform": "YouTube", "subscribers": r.get("followers"), "email": r.get("email") or "",
                     "email_source": (r.get("email_meta") or {}).get("source", ""), "verdict": c["verdict"], "lead_status": "Disqualified" if c["verdict"] == "reject" else "New",
                     "send_via": "" if not text else ("email" if r.get("email") else "DM"), "run_date": run_date})
        out.append({"handle": c["handle"], "verdict": c["verdict"], "why": c["why"], "flags": c.get("flags") or [], "geo": c["geo"],
                    "niche": c.get("niche"), "entry": c.get("entry") or [], "draft": text, "send_via": rows[-1]["send_via"]})
    with open(os.path.join(d, "contacts.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    with open(os.path.join(ROOT, "out", brand, run_date, "stage5.json"), "w") as f:
        json.dump({"brand": brand, "date": run_date, "creators": out}, f, indent=1, ensure_ascii=False)
    missing = sorted(set(hand) - {c["handle"] for c in creators})
    return d, missing, skipped
