"""Check the setup and say which parts of the engine are live. Spends no credits.

  python doctor.py          setup check, spends nothing
  python doctor.py --live   also asks YouTube whether the API key works (1 of the 10,000 daily units)
  python doctor.py --path keyless|api   record the setup the operator chose (Quick start or Full)
"""
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

ROOT = os.path.dirname(os.path.abspath(__file__))
PATH_FILE = os.path.join(ROOT, "state", "setup_path")

# What Google answers when a key does not work, and what to do about it (docs/youtube-api-key.md)
KEY_ERRORS = [
    ("API_KEY_INVALID", "not a valid key - copy it again from the Credentials page, no spaces or quotes"),
    ("keyInvalid", "not a valid key - copy it again from the Credentials page, no spaces or quotes"),
    ("SERVICE_DISABLED", "YouTube Data API v3 is not enabled in the key's project - enable it there"),
    ("accessNotConfigured", "YouTube Data API v3 is not enabled in the key's project - enable it there"),
    ("API_KEY_SERVICE_BLOCKED", "the key is restricted to other APIs - add YouTube Data API v3 to its API restrictions"),
    ("API_KEY_IP_ADDRESS_BLOCKED", "the key only allows other IP addresses - set Application restrictions to None"),
    ("API_KEY_HTTP_REFERRER_BLOCKED", "the key only allows websites - set Application restrictions to None"),
    ("quotaExceeded", "today's quota is used up - it resets at midnight Pacific time"),
]


def line(ok, name, detail):
    print("  %s  %-22s %s" % ("ok  " if ok else "MISS" if ok is False else "--  ", name, detail))


def live_key_check(yt):
    """One channels.list call for 1 unit, recorded in the quota ledger."""
    url = "https://www.googleapis.com/youtube/v3/channels?" + urllib.parse.urlencode(
        {"part": "id", "id": "UCBR8-60-B28hp2BmDPdntcQ", "key": yt.API_KEY})
    yt._ledger_add(units=1)
    try:
        json.loads(urllib.request.urlopen(url, timeout=20).read())
        return True, "works - YouTube accepted the key (1 unit used)"
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf8", "ignore")
        for marker, fix in KEY_ERRORS:
            if marker in body:
                return False, fix
        return False, "HTTP %d from YouTube - see docs/youtube-api-key.md, Troubleshooting" % e.code
    except Exception as e:
        return False, "could not reach YouTube: %s" % str(e)[:60]


def main():
    if "--path" in sys.argv:
        i = sys.argv.index("--path")
        choice = sys.argv[i + 1] if len(sys.argv) > i + 1 else ""
        if choice not in ("keyless", "api"):
            sys.exit("usage: doctor.py --path keyless|api")
        os.makedirs(os.path.dirname(PATH_FILE), exist_ok=True)
        open(PATH_FILE, "w").write(choice + "\n")
        print("setup path recorded: %s" % choice)
        return
    print("YouTube sourcing engine - setup check\n")
    print("Python")
    line(sys.version_info >= (3, 9), "python", sys.version.split()[0] + (" (3.9 or newer needed)" if sys.version_info < (3, 9) else ""))
    for mod in ("yaml", "yt_dlp"):
        try:
            __import__(mod)
            line(True, mod, "installed")
        except ImportError:
            line(False, mod, "missing - run: bash setup.sh")
    from engine.providers.http import call, env
    from engine import filters, seeds
    print("\nKeys (.env)")
    from engine.providers import yt
    serper = env("SERPER_API_KEY")
    if yt.API_KEY:
        q = yt.quota_today()
        line(True, "YOUTUBE_API_KEY", "set - official API in use; today %d of %d units and %d of %d runs used" % (q["units"], q["daily_cap"], q["runs"], q["max_api_runs"]))
        if "--live" in sys.argv:
            ok, detail = live_key_check(yt)
            line(ok, "key test", detail)
        else:
            line(None, "key test", "not run - add --live to check the key with YouTube (1 unit)")
    else:
        line(None, "YOUTUBE_API_KEY", "not set - keyless mode: slower, 15 uploads per channel instead of 50, no commenter check (a key is free)")
    line(bool(serper) or None, "SERPER_API_KEY", "set - one web search for a missing email" if serper else "not set - optional, only used to look for a missing email")
    sc = env("SCRAPECREATORS_API_KEY")
    line(bool(sc) or None, "SCRAPECREATORS_API_KEY", "set - transcripts of the top entry videos" if sc else "not set - optional, drafts refer to titles and descriptions instead of transcripts")
    print("\nSetup path")
    chosen = open(PATH_FILE).read().strip() if os.path.exists(PATH_FILE) else ""
    if yt.API_KEY:
        line(True, "path", "Full setup - free YouTube API key, 4 runs a day at no cost")
    elif chosen == "keyless":
        line(None, "path", "Quick start (keyless) by choice - upgrade any time in about 10 minutes: docs/youtube-api-key.md")
    elif chosen == "api":
        line(False, "path", "Full setup chosen, but no YOUTUBE_API_KEY in .env yet - docs/youtube-api-key.md")
    else:
        line(None, "path", "not chosen yet - Quick start (keyless) or Full setup (free API key), see docs/SETUP.md")
    print("\nKeyless YouTube reads (used without a key, and as the fallback)")
    try:
        r = yt.rss("UCBR8-60-B28hp2BmDPdntcQ")
        line(bool(r["videos"]), "RSS feed", "readable, %d uploads" % len(r["videos"]) if r["videos"] else "not readable from this network")
    except Exception as e:
        line(False, "keyless", str(e)[:80])
    print("\nBrands")
    cfgs = sorted(f[:-4] for f in os.listdir(os.path.join(ROOT, "config")) if f.endswith(".yml") and not f.startswith("_"))
    if not cfgs:
        line(None, "config", "no brand yet - give Claude your website to start")
    for b in cfgs:
        n = sum(1 for l in open(os.path.join(ROOT, "config", b + ".yml")) if "TODO" in l and not l.lstrip().startswith("#"))
        cal = os.path.exists(os.path.join(ROOT, "state", b + ".calibrated"))
        line(n == 0, b, ("ready, " + ("calibrated" if cal else "not calibrated yet (first run ends with a 20-minute calibration)")) if n == 0 else "%d TODOs left in config/%s.yml" % (n, b))
        bdir = os.path.join(ROOT, "brand", b)
        docs = [f for f in os.listdir(bdir) if not f.startswith(".") and f != "brief.md"] if os.path.isdir(bdir) else []
        brief = os.path.exists(os.path.join(bdir, "brief.md"))
        line(True if brief else None, "  brand context", ("deep: brand/%s/brief.md from %d document%s" % (b, len(docs), "" if len(docs) == 1 else "s")) if brief
             else ("%d document%s in brand/%s/, brief not written yet - ask Claude to read them" % (len(docs), "" if len(docs) == 1 else "s", b)) if docs
             else "website only - go deeper any time: ICPs, brand guidelines, what works (docs/SETUP.md)")
        sd = seeds.load(b)
        age = seeds.age_days(sd) if sd else None
        if sd:
            bst = seeds.settings(filters.Cfg(os.path.join(ROOT, "config", b + ".yml")))
            line(True, "  lateral mode", "transcripts: titles, lookalikes and transcript variations" if seeds.transcripts_on(bst) else
                 "free: titles + lookalikes" + (" - transcript mode is set but SCRAPECREATORS_API_KEY is missing" if bst["content_mode"] == "transcripts"
                                                else " (upgrade: transcript variations with a ScrapeCreators key)"))
        line(True if sd else None, "  top creators", ("%d seeds for lateral search, imported %s days ago%s" % (len(sd["seeds"]), age, " - time for a fresh import" if age and age > 60 else "")) if sd
             else "none imported - add your 5-10 best videos with their results for lateral search (docs/SETUP.md, Level 4)")
    print("\nWhat runs with this setup: %s" % ("full run on the official API" if yt.API_KEY else "full run in keyless mode (add YOUTUBE_API_KEY for the deeper checks)"))


if __name__ == "__main__":
    main()
