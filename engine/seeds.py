"""Seeds: the operator's own best YouTube videos and creators, and the lateral searches they lead to.

A seed is a creator whose videos already drove results for the brand. The engine never re-sources a
seed; it searches next to it, in two dimensions:

  CONTENT  what worked. The real titles of the top videos become searches ("seed" lane): in testing
           this found creators like the seeds far more often than anything else. For each top video
           Claude also reads the content pack (title, description, tags, transcript when available) and
           writes angles with search variations (seeds/<brand>-angles.json); those run as a small
           exploration slot, the "content" lane. The transcripts also feed the vetting and the drafts.
  CREATOR  who it worked with. Each seed has a profile: its title vocabulary, size, country and format.
           The engine searches the seed's fingerprint (its most distinctive words) and collects peer
           creators who comment on the seed's top video ("lookalike" lane). Every channel that passes
           the gates is then compared with every seed profile; a close match is flagged as a lookalike
           and ranks slightly higher.

Seeds and angles rotate on a cooldown, so consecutive runs explore different neighbourhoods. Only
results inside `seeds.window_days` count at import, profiles older than 30 days are refreshed, and
the digest warns when the import is older than `seeds.stale_days`.

  seeds/<brand>.json            written by import_seeds.py (git-ignored: the operator's own results)
  seeds/<brand>-content/*.md    the content pack per top video (untrusted text)
  seeds/<brand>-angles.json     written by Claude from the content pack
"""
import json
import math
import os
import re
from collections import Counter
from datetime import date, datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULTS = {"share": 0.4, "per_seed": 2, "content_mode": "titles", "cooldown_days": 21, "window_days": 180, "stale_days": 60,
            "suffix": "", "lookalike_min": 0.35, "peers_per_seed": 8}
PROFILE_DAYS = 30
STOP = set("the a an and or of to in on for with my your how what why this that is are was were i you we our it its "
           "vs from by at be do does did not no new best top ever full official video videos part episode ep "
           "really much huge main catch actually just get got make made need want can will one all more most very so "
           "here when who which every everything nobody anyone thing things stuff way lot lots "
           "day days week weeks month year years today vlog update live shorts short channel subscribe watch "
           "january february march april june july august september october november december christmas "
           "halloween easter summer winter spring autumn hard easy "
           "der die das und ist ich mit wie ein eine le la les et de du des pour avec mon comment "
           "el los las y en con para por una un".split())


def path(brand):
    return os.path.join(ROOT, "seeds", "%s.json" % brand)


def content_dir(brand):
    return os.path.join(ROOT, "seeds", "%s-content" % brand)


def angles_path(brand):
    return os.path.join(ROOT, "seeds", "%s-angles.json" % brand)


def settings(cfg):
    s = dict(DEFAULTS)
    s.update(cfg.get("seeds") or {})
    return s


def transcripts_on(st):
    """Transcript mode (the upgrade) needs content_mode: transcripts AND the optional ScrapeCreators key."""
    from .providers.http import env
    return st.get("content_mode") == "transcripts" and bool(env("SCRAPECREATORS_API_KEY"))


def load(brand):
    p = path(brand)
    if not os.path.exists(p):
        return None
    with open(p) as f:
        return json.load(f)


def save(brand, data):
    os.makedirs(os.path.dirname(path(brand)), exist_ok=True)
    with open(path(brand), "w") as f:
        json.dump(data, f, indent=1, ensure_ascii=False)


def _angles_file(brand):
    p = angles_path(brand)
    try:
        if not os.path.exists(p):
            return {}
        with open(p) as f:
            return json.load(f)
    except Exception:
        return {}


def load_angles(brand):
    """Content dimension, written by Claude: [{video_id, seed, angle, queries}]."""
    return _angles_file(brand).get("angles") or []


def load_creator_angles(brand):
    """Creator dimension, written by Claude: [{seed, creator, queries}] - who the seed is, as lookalike searches."""
    return _angles_file(brand).get("creators") or []


def ids(brand):
    d = load(brand)
    return {s["channel_id"]: s.get("name") or s["channel_id"] for s in (d or {}).get("seeds", [])}


def age_days(data):
    try:
        return (date.today() - datetime.strptime(data["imported"], "%Y-%m-%d").date()).days
    except Exception:
        return None


def words(text):
    t = re.sub(r"[\[\(].*?[\]\)]|#\S+|https?://\S+", " ", (text or "").lower())
    return [w for w in re.findall(r"[^\W\d_][\w'-]*", t) if w not in STOP and len(w) > 2]


def title_query(title):
    """A seed's video title -> a short search phrase a viewer might type (no emojis, brackets, hashtags, stopwords)."""
    return " ".join(words(re.sub(r"\|.*$", " ", title or ""))[:5])


def with_suffix(q, st):
    return ("%s %s" % (q, st["suffix"])).strip() if q and st["suffix"] and st["suffix"] not in q.split() else q


# --- rotation ------------------------------------------------------------------------------------

def walked(c):
    if c is None:
        return {}
    c.execute("create table if not exists seed_walks(channel_id text primary key, last_walked text)")
    return dict(c.execute("select channel_id, last_walked from seed_walks").fetchall())


def mark_walked(c, keys):
    if c is None or not keys:
        return
    c.execute("create table if not exists seed_walks(channel_id text primary key, last_walked text)")
    t = date.today().isoformat()
    c.executemany("insert into seed_walks values(?,?) on conflict(channel_id) do update set last_walked=excluded.last_walked",
                  [(x, t) for x in keys])
    c.commit()


def _days_since(walks, key):
    w = walks.get(key)
    return (date.today() - datetime.strptime(w, "%Y-%m-%d").date()).days if w else 10 ** 6


def pick(items, walks, n, cooldown_days, key):
    """Best-ranked items that are off cooldown first; when all wait, the least recently walked."""
    ready = [x for x in items if _days_since(walks, key(x)) >= cooldown_days]
    waiting = sorted([x for x in items if _days_since(walks, key(x)) < cooldown_days], key=lambda x: -_days_since(walks, key(x)))
    return (ready + waiting)[:n]


# --- creator profiles (the creator dimension) ----------------------------------------------------

def build_profile(meta, videos):
    caps = [v.get("caption") or v.get("title") or "" for v in videos]
    shorts = sum(1 for v in videos if v.get("is_short"))
    top = max(videos, key=lambda v: v.get("views") or 0) if videos else {}
    return {"fetched": date.today().isoformat(), "subs": meta.get("subs"), "country": meta.get("country"),
            "format": "shorts" if videos and shorts > len(videos) / 2 else "longform",
            "words": dict(Counter(w for c in caps for w in set(words(c))).most_common(60)),
            "top_video": top.get("id") or top.get("video_id")}


def refresh_profiles(brand, yt, max_n=10, force=False):
    """Profiles for the top seeds, refreshed when older than 30 days (about 3 quota units each). Returns how many were fetched."""
    data = load(brand)
    if not data:
        return 0
    n = 0
    for s in data["seeds"][:max_n]:
        p = s.get("profile") or {}
        fresh = p.get("fetched") and (date.today() - datetime.strptime(p["fetched"], "%Y-%m-%d").date()).days < PROFILE_DAYS
        if fresh and not force:
            continue
        meta = yt.channel_record(s["channel_id"])
        if meta.get("error"):
            continue
        s["profile"] = build_profile(meta, (yt.uploads(s["channel_id"], 50) or {}).get("videos") or [])
        s["name"] = s.get("name") or meta.get("name")
        n += 1
    if n:
        save(brand, data)
    return n


def fingerprint(profile, all_profiles, n=3):
    """The seed's most distinctive words: frequent in its titles, rarer across the other seeds."""
    w = profile.get("words") or {}
    others = [p.get("words") or {} for p in all_profiles if p is not profile]
    def weight(word):  # frequent in this seed's titles; a little lower when every seed uses it
        return w[word] * (0.7 if others and all(word in o for o in others) else 1.0)
    return [x for x in sorted(w, key=lambda k: -weight(k)) if w[x] >= 3][:n]


def similarity(profile, meta, videos):
    """0-1 match of a channel against one seed profile: topic 60%, size 20%, country 10%, format 10%."""
    sw = profile.get("words") or {}
    cw = Counter(w for v in videos for w in set(words(v.get("caption") or v.get("title") or "")))
    if not sw or not cw:
        return 0.0, []
    dot = sum(sw[k] * cw[k] for k in sw if k in cw)
    topic = dot / (math.sqrt(sum(x * x for x in sw.values())) * math.sqrt(sum(x * x for x in cw.values())) or 1)
    a, b = profile.get("subs"), meta.get("subs")
    size = max(0.0, 1 - abs(math.log10(b / a))) if a and b else 0.5
    country = 0.5 if not (profile.get("country") and meta.get("country")) else float(profile["country"] == meta["country"])
    shorts = sum(1 for v in videos if v.get("is_short"))
    fmt = float(("shorts" if videos and shorts > len(videos) / 2 else "longform") == profile.get("format"))
    shared = sorted((k for k in sw if k in cw), key=lambda k: -(sw[k] * cw[k]))[:4]
    return round(0.6 * min(1.0, topic * 1.6) + 0.2 * size + 0.1 * country + 0.1 * fmt, 2), shared


def best_lookalike(profiles, meta, videos):
    best = (0.0, None, [])
    for name, p in profiles.items():
        sim, shared = similarity(p, meta, videos)
        if sim > best[0]:
            best = (sim, name, shared)
    return best


def profiles_for(brand):
    return {s.get("name") or s["channel_id"]: s["profile"] for s in (load(brand) or {}).get("seeds", []) if s.get("profile")}


def peer_creators(yt, seed, cfg, n):
    """Creators who comment on the seed's top video: the same community. API only (needs commenter channel ids)."""
    p = seed.get("profile") or {}
    if yt.backend() != "api" or not p.get("top_video"):
        return []
    try:
        ct = yt._api("commentThreads", 1, part="snippet", videoId=p["top_video"], maxResults=100, order="relevance", textFormat="plainText")
        authors = []
        for it in ct.get("items") or []:
            a = ((it["snippet"].get("topLevelComment") or {}).get("snippet") or {}).get("authorChannelId", {}).get("value")
            if a and a != seed["channel_id"] and a not in authors:
                authors.append(a)
        if not authors:
            return []
        d = yt._api("channels", 1, part="snippet,statistics", id=",".join(authors[:50]))
    except Exception:
        return []
    band, out = cfg["band"], []
    for ch in d.get("items") or []:
        st = ch.get("statistics", {})
        subs, vids = int(st.get("subscriberCount", 0) or 0), int(st.get("videoCount", 0) or 0)
        if band["min_followers"] <= subs <= band["max_followers"] and vids >= 10:
            out.append({"channel_id": ch["id"], "channel": ch["snippet"].get("title", ""), "title": "commented on %s" % (seed.get("name") or "a seed")})
    return out[:n]


# --- the plan for one run ------------------------------------------------------------------------

def plan(cfg, brand, c, n_searches, rss, relevant):
    """Lateral queries for this run: [(lane, phrase, seed name)], the rotation keys used, and a status line.

    The lateral budget is split by what tested best (config `seeds.split`):
      titles     45%  "seed" lane: the real titles of the top videos, then the seeds' top on-topic uploads
      lookalike  40%  "lookalike" lane: Claude's creator descriptions, else each seed's title fingerprint
      variations 15%  "content" lane: Claude's transcript-based variations, a small exploration slot
    A lane that runs short hands its slots to the others in that order. The variations slot only runs in
    transcript mode (`seeds.content_mode: transcripts` plus a ScrapeCreators key); the free default gives
    the whole lateral budget to titles and lookalikes. rss(channel_id) is the free feed;
    relevant(text) keeps a seed's off-topic uploads from steering the search."""
    data = load(brand)
    if not data or not data.get("seeds"):
        return [], [], "no seeds imported (import your best videos or creators to add lateral searches)"
    st = settings(cfg)
    walks = walked(c)
    n_q = int(round(n_searches * st["share"]))
    queries, used, seen_q = [], [], set()

    def ok(q):
        return q and len(q.split()) >= 3 and with_suffix(q, st) not in seen_q  # two words are too vague

    def take(lane, q, who, key):
        q2 = with_suffix(q, st)
        seen_q.add(q2)
        queries.append((lane, q2, who))
        if key and key not in used:
            used.append(key)

    def rot(items, key):
        return pick(items, walks, len(items), st["cooldown_days"], key)

    def titles_pool():  # lazily: imported titles first, then the free feed only if still needed
        vids = [dict(v, seed=s.get("name") or s["channel_id"]) for s in data["seeds"] for v in s.get("videos") or [] if v.get("title")]
        for v in rot(vids, lambda v: "title:" + v["video_id"]):
            yield ("seed", title_query(v["title"]), v["seed"], "title:" + v["video_id"])
        for sd in rot(data["seeds"], lambda x: x["channel_id"]):
            feed = rss(sd["channel_id"]).get("videos") or []
            for v in [v for v in sorted(feed, key=lambda v: -(v.get("views") or 0)) if relevant(v["title"])][:max(1, int(st["per_seed"]))]:
                yield ("seed", title_query(v["title"]), sd.get("name") or sd["channel_id"], sd["channel_id"])

    def lookalike_pool():
        cas = load_creator_angles(brand)
        if cas:
            for ca in rot(cas, lambda x: "fp:" + (x.get("seed") or "")):
                for q in ca.get("queries") or []:
                    yield ("lookalike", q, ca.get("seed") or "your top creator", "fp:" + (ca.get("seed") or ""))
                    break  # one per creator per run; the next run takes the next creator
            return
        profs = [x for x in data["seeds"] if x.get("profile")]
        for sd in rot(profs, lambda x: "fp:" + x["channel_id"]):
            fp = fingerprint(sd["profile"], [x["profile"] for x in profs])
            if len(fp) >= 2:
                yield ("lookalike", " ".join(fp), sd.get("name") or sd["channel_id"], "fp:" + sd["channel_id"])

    angles = load_angles(brand)

    def variations_pool():
        for a in rot(angles, lambda a: "angle:" + a.get("video_id", a.get("angle", ""))):
            for q in a.get("queries") or []:
                if ok(q):
                    yield ("content", q, a.get("seed") or "your top video", "angle:" + a.get("video_id", a.get("angle", "")))
                    break  # one variation per video per run

    sp = dict({"titles": 0.45, "lookalike": 0.40, "variations": 0.15}, **(st.get("split") or {}))
    deep = transcripts_on(st)
    if not deep:  # the free default: titles and lookalikes share the whole lateral budget
        sp["variations"] = 0
    n_var = max(1, int(round(n_q * sp["variations"]))) if (angles and deep) else 0
    n_look = int(round(n_q * sp["lookalike"] / ((sp["titles"] + sp["lookalike"]) or 1) * (1 - (sp["variations"] if deep else 0))))
    want = {"seed": n_q - n_var - n_look, "lookalike": n_look, "content": n_var}
    pools = {"seed": titles_pool(), "lookalike": lookalike_pool(), "content": variations_pool()}

    def fill(lane, n):
        got = 0
        for item in pools[lane]:
            if got >= n or len(queries) >= n_q:
                break
            if ok(item[1]):
                take(*item)
                got += 1
        return got

    short = 0
    for lane in ("seed", "lookalike", "content"):
        short += want[lane] - fill(lane, want[lane])
    for lane in ("seed", "lookalike", "content") if deep else ("seed", "lookalike"):  # hand unused slots on
        if short <= 0:
            break
        short -= fill(lane, short)
    age = age_days(data)
    lanes = Counter(l for l, _, _ in queries)
    names = {"seed": "real titles", "lookalike": "lookalike", "content": "transcript variations"}
    mode = "transcripts" if deep else "free: titles + lookalikes" + (" (transcript mode is on but there is no ScrapeCreators key)" if st["content_mode"] == "transcripts" else "")
    status = "%d lateral searches (%s), mode %s, from %d seeds and %d angles (imported %s%s)" % (
        len(queries), ", ".join("%s %d" % (names[k], v) for k, v in lanes.items()) or "none", mode, len(data["seeds"]), len(angles), data.get("imported"),
        ", %d days ago: refresh it with your latest results" % age if age is not None and age > st["stale_days"] else "")
    return queries, used, status


def peers(cfg, brand, yt, c):
    """Peer creators for this run's seeds (creator dimension, API only), rotating like the searches."""
    data = load(brand)
    if not data:
        return [], []
    st = settings(cfg)
    walks = walked(c)
    profs = [s for s in data["seeds"] if (s.get("profile") or {}).get("top_video")]
    rows, used = [], []
    for s in pick(profs, walks, 3, st["cooldown_days"], lambda s: "peer:" + s["channel_id"]):
        got = peer_creators(yt, s, cfg, st["peers_per_seed"])
        for r in got:
            rows.append(dict(r, seed=s.get("name") or s["channel_id"]))
        used.append("peer:" + s["channel_id"])
    return rows, used
