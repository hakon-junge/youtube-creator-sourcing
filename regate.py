"""Re-apply the current gates and scoring to a past run, without spending any quota.

  python regate.py --brand <slug> [--date YYYY-MM-DD]

phase1 saves what it found (discovery.json) and each channel's record and upload history
(enrichment.json). This replays the gates on that saved data with today's config and code.
Comment-check results already on a record are carried over. The only network use is the free
link-page fetch. The previous results file is kept as results_before_regate.json.
"""
import argparse
import copy
import json
import os
import shutil
import sys
from collections import Counter
from datetime import date

import phase1
from engine import emails, filters, seeds, store

ROOT = os.path.dirname(os.path.abspath(__file__))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--brand", required=True)
    ap.add_argument("--date", default=str(date.today()))
    a = ap.parse_args()
    cfg = filters.Cfg(os.path.join(ROOT, "config", "%s.yml" % a.brand))
    cfg.seed_ids = seeds.ids(a.brand)
    cfg.seed_profiles = seeds.profiles_for(a.brand)
    d = os.path.join(ROOT, "out", a.brand, a.date)
    path, keep = os.path.join(d, "results.json"), os.path.join(d, "results_before_regate.json")
    if not os.path.exists(keep):
        shutil.copy(path, keep)
    data = json.load(open(path))
    cands = json.load(open(os.path.join(d, "discovery.json")))["candidates"]
    enr = json.load(open(os.path.join(d, "enrichment.json")))
    emails.serper.available = lambda: False  # no paid search in a re-gate
    old = {r["channel_id"]: r for r in data["results"]}
    moved = Counter()
    for cid, e in enr.items():
        prev = old.get(cid, {})
        if prev.get("lane") == "skip_seen":
            continue
        new = phase1.judge(cfg, cands[cid], e["meta"], copy.deepcopy(e["videos"]))
        if new["lane"] in ("review", "auto"):
            if not new.get("email") and prev.get("email"):  # an address found by search last time
                new.update(email=prev["email"], email_meta=prev["email_meta"], emails_found=prev.get("emails_found"))
            if prev.get("audience"):
                new["audience"], new["deep"] = prev["audience"], prev.get("deep")
                if prev.get("audience_geo"):  # carried over as it was; a changed audience target needs a new deep check
                    new["audience_geo"] = prev["audience_geo"]
                for p, q in zip(new.get("entry_posts") or [], prev.get("entry_posts") or []):
                    if p["url"] == q["url"] and q.get("transcript"):
                        p["transcript"] = q["transcript"]
            new["score"], new["score_why"] = phase1.score(cfg, new)
        if prev.get("lane") != new["lane"]:
            moved["%s -> %s" % (prev.get("lane"), new["lane"])] += 1
            print("  %-28s %s -> %s (%s)" % (new["handle"][:28], prev.get("lane"), new["lane"], new["reason"]), flush=True)
        old[cid] = new
    data["results"] = list(old.values())
    passed = [r for r in data["results"] if r["lane"] in ("review", "auto")]
    dg = data["digest"]
    dg["lanes"] = dict(Counter(r["lane"] for r in data["results"]))
    dg["reject_reasons"] = dict(Counter(r["reason"].split(":")[0] for r in data["results"] if r["lane"] == "reject").most_common())
    dg["passed"], dg["with_email"] = len(passed), sum(1 for r in passed if r.get("email"))
    dg["email_steps"] = dict(Counter(r["email_meta"]["step"] for r in passed if r.get("email_meta")))
    dg["regate"] = {"moved": dict(moved)}
    store.dump_json(data, path)
    print("regate: %d pass (%d with email) | moved: %s" % (len(passed), dg["with_email"], dict(moved) or "nothing"))


if __name__ == "__main__":
    sys.exit(main())
