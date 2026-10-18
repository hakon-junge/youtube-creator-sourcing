"""Keyless YouTube backend.

No Data API key. Three free sources, cheapest first:
  - search:        yt-dlp "ytsearchN:" flat results (channel id, name, video title)
  - channel meta:  yt-dlp flat /videos tab (subs, handle, description, recent ids)
  - RSS:           youtube.com/feeds/videos.xml (15 latest: published, views, likes, description)
  - deep:          yt-dlp single-video extract with comments (player_client=tv, no formats)

Everything is polite by default: a fixed sleep between network calls. There is
no quota to burn, but there is a rate limit to respect. Do not remove the sleep.
"""
import re
import time
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET

import yt_dlp

SLEEP = 1.2  # seconds between calls
_last = [0.0]

NS = {
    "a": "http://www.w3.org/2005/Atom",
    "yt": "http://www.youtube.com/xml/schemas/2015",
    "media": "http://search.yahoo.com/mrss/",
}


def _pace():
    wait = SLEEP - (time.time() - _last[0])
    if wait > 0:
        time.sleep(wait)
    _last[0] = time.time()


def _ydl(extra=None):
    opts = {
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
        "socket_timeout": 20,
        "ignore_no_formats_error": True,
        # the default web client hits "page needs to be reloaded" (SABR); tv does not
        "extractor_args": {"youtube": {"player_client": ["tv"]}},
    }
    if extra:
        opts.update(extra)
    return yt_dlp.YoutubeDL(opts)


def search(query, n=20):
    """Flat video search. Returns [{video_id, title, channel_id, channel, channel_url}]."""
    _pace()
    with _ydl({"extract_flat": True}) as y:
        try:
            d = y.extract_info("ytsearch%d:%s" % (n, query), download=False)
        except Exception as e:  # network / parse failures never kill a run
            return {"error": str(e)[:200], "rows": []}
    rows = []
    for e in d.get("entries") or []:
        if not e or not e.get("channel_id"):
            continue
        rows.append({
            "video_id": e.get("id"),
            "title": e.get("title") or "",
            "channel_id": e.get("channel_id"),
            "channel": e.get("channel") or e.get("uploader") or "",
            "channel_url": e.get("channel_url") or "https://www.youtube.com/channel/%s" % e.get("channel_id"),
            "views": e.get("view_count"),
        })
    return {"error": None, "rows": rows}


def channel_meta(channel_id, n=30):
    """Subs, handle, description and recent video ids from the /videos tab."""
    _pace()
    url = "https://www.youtube.com/channel/%s/videos" % channel_id
    with _ydl({"extract_flat": True, "playlistend": n}) as y:
        try:
            d = y.extract_info(url, download=False)
        except Exception as e:
            return {"error": str(e)[:200]}
    return {
        "error": None,
        "channel_id": channel_id,
        "name": d.get("channel") or d.get("uploader") or "",
        "handle": (d.get("uploader_id") or "").lstrip("@").lower(),
        "subs": d.get("channel_follower_count"),
        "description": d.get("description") or "",
        "tags": d.get("tags") or [],
        "video_ids": [e.get("id") for e in (d.get("entries") or []) if e],
    }


def shorts_ids(channel_id, n=30):
    """Ids on the /shorts tab, so RSS stats can exclude them. Empty on any failure."""
    _pace()
    url = "https://www.youtube.com/channel/%s/shorts" % channel_id
    with _ydl({"extract_flat": True, "playlistend": n}) as y:
        try:
            d = y.extract_info(url, download=False)
        except Exception:
            return set()
    return {e.get("id") for e in (d.get("entries") or []) if e}


def rss(channel_id):
    """15 latest uploads with published date, views, likes and description."""
    _pace()
    url = "https://www.youtube.com/feeds/videos.xml?channel_id=%s" % channel_id
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        xml = urllib.request.urlopen(req, timeout=20).read()
        root = ET.fromstring(xml)
    except Exception as e:
        return {"error": str(e)[:200], "videos": []}
    vids = []
    for en in root.findall("a:entry", NS):
        g = en.find("media:group", NS)
        stats = g.find("media:community/media:statistics", NS) if g is not None else None
        rating = g.find("media:community/media:starRating", NS) if g is not None else None
        desc = g.find("media:description", NS) if g is not None else None
        vids.append({
            "video_id": en.findtext("yt:videoId", default="", namespaces=NS),
            "title": en.findtext("a:title", default="", namespaces=NS),
            "published": en.findtext("a:published", default="", namespaces=NS)[:10],
            "views": int(stats.get("views")) if stats is not None and stats.get("views") else None,
            "likes": int(rating.get("count")) if rating is not None and rating.get("count") else None,
            "description": (desc.text or "") if desc is not None else "",
        })
    return {"error": None, "videos": vids}


def video_detail(video_id, max_comments=40):
    """Views, true comment total, upload date, and top comments incl. a few replies.

    Two calls on purpose: with getcomments on, yt-dlp overwrites comment_count with
    the number of comments it fetched, so the true total comes from a plain extract.
    """
    url = "https://www.youtube.com/watch?v=%s" % video_id
    _pace()
    with _ydl() as y:
        try:
            d = y.extract_info(url, download=False)
        except Exception as e:
            return {"error": str(e)[:200]}
    _pace()
    extra = {
        "getcomments": True,
        "extractor_args": {"youtube": {
            "player_client": ["tv"],
            "max_comments": [str(max_comments), "all", "20", "5"],
            "comment_sort": ["top"],
        }},
    }
    comments = []
    with _ydl(extra) as y:
        try:
            dc = y.extract_info(url, download=False)
            raw = dc.get("comments") or []
        except Exception:
            raw = []
    for c in raw:
        comments.append({
            "text": c.get("text") or "",
            "is_uploader": bool(c.get("author_is_uploader")),
            "is_reply": c.get("parent") not in (None, "root"),
            "likes": c.get("like_count") or 0,
        })
    return {
        "error": None,
        "video_id": video_id,
        "title": d.get("title") or "",
        "views": d.get("view_count"),
        "comment_count": d.get("comment_count"),
        "likes": d.get("like_count"),
        "duration": d.get("duration"),
        "upload_date": d.get("upload_date"),
        "language": d.get("language"),
        "description": d.get("description") or "",
        "comments": comments,
    }


EMAIL_RX = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")


def public_emails(*texts):
    """Emails printed in the creator's own description. Never guessed."""
    found = []
    for t in texts:
        for m in EMAIL_RX.findall(t or ""):
            if m.lower() not in found:
                found.append(m.lower())
    return found


# ---------------------------------------------------------------------------
# Optional YouTube Data API v3 backend. Used automatically when YOUTUBE_API_KEY
# is set (env or .env). Faster, stable, and returns reply authors, so creator
# reply-rate becomes measurable. Every call falls back to the keyless path on
# any API error (quota, network), so a run never dies on the API.
#
# Unit cost (10,000/day free): search 100 | channels, playlistItems, videos,
# commentThreads 1 each. A 14-search run with ~170 channels is roughly 2,500.
# ---------------------------------------------------------------------------
import json as _json
import os as _os
import urllib.parse as _up

_ROOT = _os.path.dirname(_os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))


def _load_key():
    k = _os.environ.get("YOUTUBE_API_KEY")
    p = _os.path.join(_ROOT, ".env")
    if not k and _os.path.exists(p):
        with open(p) as f:
            for line in f:
                if line.strip().startswith("YOUTUBE_API_KEY="):
                    k = line.split("=", 1)[1].strip().strip('"').strip("'")
    return k or None


API_KEY = _load_key()
API_UNITS = [0]
API_DISABLED = [False]


def backend():
    return "api" if API_KEY and not API_DISABLED[0] else "keyless"


# --- quota guard -----------------------------------------------------------------
# Free quota: 10,000 units/day, resetting at midnight Pacific time. Hard rules:
#   - the day never goes past DAILY_CAP (safety margin under 10,000)
#   - at most MAX_API_RUNS engine runs per Pacific day use the API; each gets RUN_CAP units
#   - anything over a cap falls back to the keyless path - a run finishes, it never overspends
# Ledger: state/youtube_quota.json  {"<pacific date>": {"units": n, "runs": n}}
DAILY_CAP, MAX_API_RUNS = 9600, 4
RUN_CAP = DAILY_CAP // MAX_API_RUNS
_LEDGER = _os.path.realpath(_os.path.join(_ROOT, "state", "youtube_quota.json"))  # a symlinked ledger stays shared
_RUN = {"active": False, "tag": None}


def _pacific_day():
    from datetime import datetime
    from zoneinfo import ZoneInfo
    return datetime.now(ZoneInfo("America/Los_Angeles")).strftime("%Y-%m-%d")


def _ledger_read():
    try:
        with open(_LEDGER) as f:
            return _json.load(f)
    except Exception:
        return {}


def _ledger_add(units=0, runs=0, tag=None):
    d = _ledger_read(); day = _pacific_day()
    rec = d.setdefault(day, {"units": 0, "runs": 0})
    rec["units"] += units; rec["runs"] += runs
    tag = tag or (_RUN.get("tag") if _RUN.get("active") else None)
    if tag:
        ru = rec.setdefault("run_units", {})
        ru[tag] = ru.get(tag, 0) + units
    d = {k: v for k, v in sorted(d.items())[-14:]}  # keep two weeks
    _os.makedirs(_os.path.dirname(_LEDGER), exist_ok=True)
    tmp = _LEDGER + ".tmp"
    with open(tmp, "w") as f:  # closed (flushed) before it replaces the ledger
        _json.dump(d, f, indent=1)
    _os.replace(tmp, _LEDGER)
    return rec


def quota_today():
    rec = _ledger_read().get(_pacific_day(), {"units": 0, "runs": 0})
    return dict(rec, day=_pacific_day(), daily_cap=DAILY_CAP, max_api_runs=MAX_API_RUNS, run_cap=RUN_CAP)


def _run_tag():
    return _os.environ.get("YT_RUN_TAG") or ""


def start_run():
    """Claim one of today's API runs for this brand run. All processes sharing YT_RUN_TAG (set by run_brand.sh)
    join the same run and share its RUN_CAP; a process without a tag claims its own run.
    Returns a status line; disables the API for this process when no run is available."""
    if not API_KEY:
        return "keyless (no YOUTUBE_API_KEY)"
    tag = _run_tag() or "solo-%d" % _os.getpid()
    d = _ledger_read(); day = _pacific_day()
    rec = d.get(day, {"units": 0, "runs": 0})
    if tag in rec.get("run_units", {}):
        _RUN.update(active=True, tag=tag)
        return "api: joined run %s (%d of %d units used)" % (tag, rec["run_units"][tag], RUN_CAP)
    if rec["runs"] >= MAX_API_RUNS or rec["units"] + 100 > DAILY_CAP:
        API_DISABLED[0] = True
        return "keyless: today's %d API runs / %d units are used (resets midnight Pacific)" % (MAX_API_RUNS, DAILY_CAP)
    _ledger_add(runs=1, tag=tag)
    _RUN.update(active=True, tag=tag)
    return "api: run %d of %d today, budget %d units (%d used today)" % (rec["runs"] + 1, MAX_API_RUNS, RUN_CAP, rec["units"])


def join_run():
    """For helper steps (seeds, regate, research): share the brand run's budget when run_brand.sh set a tag."""
    return start_run() if _run_tag() else "api: untagged helper (daily cap only)"


def _run_units():
    if not _RUN.get("active"):
        return 0
    return _ledger_read().get(_pacific_day(), {}).get("run_units", {}).get(_RUN["tag"], 0)


def _allowed(units):
    q = quota_today()
    if q["units"] + units > DAILY_CAP:
        return False
    if _RUN.get("active") and _run_units() + units > RUN_CAP:
        return False
    return True


def _api(endpoint, units, **params):
    if not _allowed(units):
        API_DISABLED[0] = True  # over a cap: keyless for the rest of this process, never overspend
        raise RuntimeError("youtube quota guard: cap reached")
    params["key"] = API_KEY
    url = "https://www.googleapis.com/youtube/v3/%s?%s" % (endpoint, _up.urlencode(params))
    try:
        r = urllib.request.urlopen(urllib.request.Request(url), timeout=20)
    except urllib.error.HTTPError as e:
        _ledger_add(units=units)  # failed calls still cost quota
        body = e.read().decode("utf8", "ignore")
        if "quotaExceeded" in body or "dailyLimitExceeded" in body or e.code in (400, 403):
            API_DISABLED[0] = True
        raise
    API_UNITS[0] += units
    _ledger_add(units=units)
    return _json.loads(r.read())


def _iso_dur(s):
    m = re.match(r"P(?:(\d+)D)?T?(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", s or "")
    if not m:
        return None
    d, h, mi, se = (int(x) if x else 0 for x in m.groups())
    return d * 86400 + h * 3600 + mi * 60 + se


_k_search, _k_channel_meta, _k_shorts_ids, _k_video_detail = search, channel_meta, shorts_ids, video_detail
_DUR = {}  # video_id -> seconds, filled by channel_meta so shorts_ids is free


def search(query, n=20):
    if backend() != "api":
        return _k_search(query, n)
    try:
        d = _api("search", 100, part="snippet", q=query, type="video", maxResults=min(n, 50))
    except Exception:
        return _k_search(query, n)
    rows = []
    for it in d.get("items", []):
        sn = it["snippet"]
        rows.append({"video_id": it["id"]["videoId"], "title": sn.get("title", ""), "channel_id": sn["channelId"],
                     "channel": sn.get("channelTitle", ""), "views": None,
                     "channel_url": "https://www.youtube.com/channel/%s" % sn["channelId"]})
    return {"error": None, "rows": rows}


def channel_meta(channel_id, n=30):
    """Same shape as the keyless version; video_ids are LONG-FORM only (> 3 min)."""
    if backend() != "api":
        return _k_channel_meta(channel_id, n)
    try:
        d = _api("channels", 1, part="snippet,statistics,contentDetails", id=channel_id)
        if not d.get("items"):
            return {"error": "channel not found"}
        ch = d["items"][0]
        up = ch["contentDetails"]["relatedPlaylists"]["uploads"]
        pl = _api("playlistItems", 1, part="contentDetails", playlistId=up, maxResults=min(n, 50))
        ids = [x["contentDetails"]["videoId"] for x in pl.get("items", [])]
        vids = _api("videos", 1, part="contentDetails", id=",".join(ids)) if ids else {"items": []}
        for v in vids.get("items", []):
            _DUR[v["id"]] = _iso_dur(v["contentDetails"].get("duration"))
    except Exception:
        return _k_channel_meta(channel_id, n)
    st = ch.get("statistics", {})
    return {
        "error": None, "channel_id": channel_id,
        "name": ch["snippet"].get("title", ""),
        "handle": (ch["snippet"].get("customUrl") or "").lstrip("@").lower(),
        "subs": None if st.get("hiddenSubscriberCount") else int(st.get("subscriberCount", 0)),
        "description": ch["snippet"].get("description", ""),
        "country": ch["snippet"].get("country"),
        "tags": [],
        "video_ids": [i for i in ids if (_DUR.get(i) or 0) > 180],
    }


def shorts_ids(channel_id, n=30):
    if backend() != "api":
        return _k_shorts_ids(channel_id, n)
    return {i for i, s in _DUR.items() if s is not None and s <= 180}


def video_detail(video_id, max_comments=40):
    if backend() != "api":
        return _k_video_detail(video_id, max_comments)
    try:
        d = _api("videos", 1, part="snippet,statistics,contentDetails", id=video_id)
        if not d.get("items"):
            return {"error": "video not found"}
        v = d["items"][0]
        owner = v["snippet"]["channelId"]
        comments = []
        try:
            ct = _api("commentThreads", 1, part="snippet,replies", videoId=video_id, maxResults=min(max_comments, 100),
                      order="relevance", textFormat="plainText")
            for t in ct.get("items", []):
                top = t["snippet"]["topLevelComment"]["snippet"]
                comments.append({"text": top.get("textDisplay", ""), "is_uploader": top.get("authorChannelId", {}).get("value") == owner,
                                 "is_reply": False, "likes": top.get("likeCount", 0)})
                for r in (t.get("replies") or {}).get("comments", []):
                    rs = r["snippet"]
                    comments.append({"text": rs.get("textDisplay", ""), "is_uploader": rs.get("authorChannelId", {}).get("value") == owner,
                                     "is_reply": True, "likes": rs.get("likeCount", 0)})
        except Exception:
            pass  # comments disabled on this video
    except Exception:
        return _k_video_detail(video_id, max_comments)
    st, sn = v.get("statistics", {}), v["snippet"]
    return {
        "error": None, "video_id": video_id, "title": sn.get("title", ""),
        "views": int(st["viewCount"]) if "viewCount" in st else None,
        "comment_count": int(st["commentCount"]) if "commentCount" in st else None,
        "likes": int(st["likeCount"]) if "likeCount" in st else None,
        "duration": _iso_dur(v["contentDetails"].get("duration")),
        "upload_date": sn.get("publishedAt", "")[:10].replace("-", ""),
        "language": sn.get("defaultAudioLanguage") or sn.get("defaultLanguage"),
        "description": sn.get("description", ""),
        "comments": comments,
    }


# ---------------------------------------------------------------------------
# History, comment threads, commenter accounts and transcripts. The first three use the Data API
# (1 unit per call) and fall back to the keyless sources; transcripts are always keyless.
# ---------------------------------------------------------------------------

def _ts(iso):
    import calendar
    try:
        return calendar.timegm(time.strptime((iso or "")[:19], "%Y-%m-%dT%H:%M:%S"))
    except ValueError:
        return None


def uploads(channel_id, n=50):
    """The channel's latest uploads with title, description, views, likes, comment count and length.

    API: 2 units for 50 videos (the uploads playlist id is the channel id with UU for UC, so no
    lookup is needed). Keyless: the 15 videos in the RSS feed, with Shorts marked from the /shorts tab.
    Returns {"error", "videos": [...], "source"}.
    """
    if backend() == "api":
        try:
            pl = _api("playlistItems", 1, part="contentDetails", playlistId="UU" + channel_id[2:], maxResults=min(n, 50))
            ids = [x["contentDetails"]["videoId"] for x in pl.get("items", [])]
            d = _api("videos", 1, part="snippet,statistics,contentDetails", id=",".join(ids)) if ids else {"items": []}
            vids = []
            for v in d.get("items", []):
                sn, st = v["snippet"], v.get("statistics", {})
                dur = _iso_dur(v["contentDetails"].get("duration"))
                vids.append({"id": v["id"], "url": "https://www.youtube.com/watch?v=%s" % v["id"], "caption": sn.get("title", ""),
                             "description": sn.get("description", ""), "ts": _ts(sn.get("publishedAt")),
                             "views": int(st["viewCount"]) if "viewCount" in st else None, "likes": int(st["likeCount"]) if "likeCount" in st else None,
                             "comments": int(st["commentCount"]) if "commentCount" in st else None, "duration": dur,
                             "is_short": dur is not None and dur <= 180, "language": sn.get("defaultAudioLanguage") or sn.get("defaultLanguage")})
            return {"error": None, "videos": vids, "source": "api"}
        except Exception:
            pass
    r = rss(channel_id)
    shorts = shorts_ids(channel_id) if r["videos"] else set()
    vids = [{"id": v["video_id"], "url": "https://www.youtube.com/watch?v=%s" % v["video_id"], "caption": v["title"], "description": v["description"],
             "ts": _ts(v["published"] + "T00:00:00"), "views": v["views"], "likes": v["likes"], "comments": None, "duration": None,
             "is_short": v["video_id"] in shorts, "language": None} for v in r["videos"]]
    return {"error": r["error"], "videos": vids, "source": "rss"}


def comment_threads(video_id, n=100):
    """Top comments with author channel ids and whether the creator replied. 1 unit for up to 100 threads.
    Keyless fallback returns comments without author ids."""
    if backend() == "api":
        try:
            v = _api("videos", 1, part="snippet", id=video_id)
            owner = v["items"][0]["snippet"]["channelId"] if v.get("items") else None
            ct = _api("commentThreads", 1, part="snippet,replies", videoId=video_id, maxResults=min(n, 100), order="relevance", textFormat="plainText")
            rows = []
            for t in ct.get("items", []):
                top = t["snippet"]["topLevelComment"]["snippet"]
                replies = (t.get("replies") or {}).get("comments", [])
                rows.append({"text": top.get("textDisplay", ""), "handle": top.get("authorDisplayName", ""), "author_id": (top.get("authorChannelId") or {}).get("value"),
                             "ts": top.get("publishedAt"),
                             "likes": top.get("likeCount", 0), "replies": t["snippet"].get("totalReplyCount", 0),
                             "creator_liked": any((r["snippet"].get("authorChannelId") or {}).get("value") == owner for r in replies),
                             "is_creator": (top.get("authorChannelId") or {}).get("value") == owner})
            published = v["items"][0]["snippet"].get("publishedAt") if v.get("items") else None
            return {"error": None, "rows": [r for r in rows if not r["is_creator"]], "source": "api", "published": published}
        except Exception as e:
            if "commentsDisabled" in str(e):
                return {"error": "comments disabled", "rows": [], "source": "api"}
    d = video_detail(video_id, min(n, 40))
    if d.get("error"):
        return {"error": d["error"], "rows": [], "source": "keyless"}
    tops = [c for c in d["comments"] if not c["is_reply"] and not c["is_uploader"]]
    replied = sum(1 for c in d["comments"] if c["is_reply"] and c["is_uploader"])
    rows = [{"text": c["text"], "handle": "", "author_id": None, "likes": c["likes"], "replies": 0, "creator_liked": i < replied, "is_creator": False} for i, c in enumerate(tops)]
    return {"error": None, "rows": rows, "source": "keyless"}


def channels_brief(ids):
    """Subscriber count, video count and creation date for up to 50 channels in one unit. {} without the API."""
    ids = [i for i in ids if i][:50]
    if backend() != "api" or not ids:
        return {}
    try:
        d = _api("channels", 1, part="snippet,statistics", id=",".join(ids))
    except Exception:
        return {}
    out = {}
    for ch in d.get("items", []):
        st = ch.get("statistics", {})
        out[ch["id"]] = {"subs": None if st.get("hiddenSubscriberCount") else int(st.get("subscriberCount", 0)), "videos": int(st.get("videoCount", 0)),
                         "created": _ts(ch["snippet"].get("publishedAt")), "country": ch["snippet"].get("country")}
    return out


def comment_sample(video_id, n=100):
    """Comment text, time and author for the audience-geography estimate: 1 unit, API only ([] without a key).
    order=relevance spreads the sample over the video's life instead of the last few hours."""
    if backend() != "api":
        return []
    try:
        ct = _api("commentThreads", 1, part="snippet", videoId=video_id, maxResults=min(n, 100), order="relevance", textFormat="plainText")
    except Exception:
        return []
    out = []
    for t in ct.get("items", []):
        top = t["snippet"]["topLevelComment"]["snippet"]
        out.append({"text": top.get("textDisplay", ""), "ts": top.get("publishedAt"), "author_id": (top.get("authorChannelId") or {}).get("value")})
    return out


def commenter_countries(ids):
    """Counter of the country set on each commenter's own channel (None when not set), up to 150 commenters, 1 unit per 50."""
    from collections import Counter
    ids = list(dict.fromkeys(i for i in ids if i))[:150]
    c = Counter()
    for k in range(0, len(ids), 50):
        for b in channels_brief(ids[k:k + 50]).values():
            c[b.get("country")] += 1
    return c


def transcript(video_id, langs=("en",), max_chars=6000):
    """Spoken words of a video. "" when none could be read.

    YouTube refuses caption downloads from plain requests (HTTP 429), so the reliable source is the
    optional ScrapeCreators transcript call (1 credit, under the `scrapecreators` cap). Without that
    key the function returns "" and the note says no transcript was read.
    """
    from .. import ledger
    from .http import call, env
    if not env("SCRAPECREATORS_API_KEY") or not ledger.allowed("scrapecreators", 1):
        return ""
    st, d = call("https://api.scrapecreators.com/v1/youtube/video/transcript?" + _up.urlencode({"url": "https://www.youtube.com/watch?v=%s" % video_id}),
                 {"x-api-key": env("SCRAPECREATORS_API_KEY")}, timeout=90)
    if st != 200:
        return ""
    ledger.charge("scrapecreators", d.get("credits_charged") if d.get("credits_charged") is not None else 1, "deep", "youtube/video/transcript")
    return re.sub(r"\s+", " ", d.get("transcript_only_text") or "").strip()[:max_chars]


def channel_record(channel_id):
    """Name, handle, subscribers, about text and country for one unit (no upload ids).
    Falls back to the keyless channel read."""
    if backend() == "api":
        try:
            d = _api("channels", 1, part="snippet,statistics", id=channel_id)
            if not d.get("items"):
                return {"error": "channel not found"}
            ch = d["items"][0]
            st = ch.get("statistics", {})
            return {"error": None, "channel_id": channel_id, "name": ch["snippet"].get("title", ""),
                    "handle": (ch["snippet"].get("customUrl") or "").lstrip("@").lower(),
                    "subs": None if st.get("hiddenSubscriberCount") else int(st.get("subscriberCount", 0)),
                    "description": ch["snippet"].get("description", ""), "country": ch["snippet"].get("country"),
                    "video_count": int(st.get("videoCount", 0))}
        except Exception:
            pass
    return _k_channel_meta(channel_id, 5)
