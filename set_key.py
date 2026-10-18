"""Paste a key into .env without opening the file. The key is never shown on screen or to Claude.

Run it yourself, in a terminal, from the engine's folder:

  .venv/bin/python set_key.py                  the YouTube Data API key (then tests it: 1 of 10,000 daily units)
  .venv/bin/python set_key.py serper           the optional Serper key
  .venv/bin/python set_key.py scrapecreators   the optional ScrapeCreators key

It asks you to paste the key (nothing appears while you paste, that is normal), checks it looks
right, writes it to .env (readable only by you) and, for YouTube, asks YouTube whether it works.
"""
import getpass
import os
import re
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
ENV = os.path.join(ROOT, ".env")
KEYS = {
    "youtube": ("YOUTUBE_API_KEY", "YouTube API key", re.compile(r"^AIza[0-9A-Za-z_\-]{35}$"),
                "a YouTube key is 39 characters and starts with AIza"),
    "serper": ("SERPER_API_KEY", "Serper key", re.compile(r"^[0-9a-f]{40}$"), "a Serper key is 40 letters and digits"),
    "scrapecreators": ("SCRAPECREATORS_API_KEY", "ScrapeCreators key", re.compile(r"^\S{16,}$"), "a ScrapeCreators key has no spaces"),
}


def write_key(name, value):
    lines = []
    if os.path.exists(ENV):
        with open(ENV) as f:
            lines = f.read().splitlines()
    out, done = [], False
    for l in lines:
        if l.strip().startswith(name + "="):
            out.append("%s=%s" % (name, value))
            done = True
        else:
            out.append(l)
    if not done:
        out.append("%s=%s" % (name, value))
    old = os.umask(0o077)
    try:
        with open(ENV, "w") as f:
            f.write("\n".join(out) + "\n")
    finally:
        os.umask(old)
    os.chmod(ENV, 0o600)


def main():
    which = (sys.argv[1] if len(sys.argv) > 1 else "youtube").lower()
    if which not in KEYS:
        sys.exit("usage: set_key.py [youtube|serper|scrapecreators]")
    name, label, rx, hint = KEYS[which]
    if not sys.stdin.isatty():
        sys.exit("Run this yourself in a terminal so you can paste the key privately. Claude cannot run it for you.")
    print("\nPaste your %s and press Enter." % label)
    print("Nothing will appear on screen while you paste. That is normal: it keeps the key private.\n")
    for attempt in range(3):
        key = getpass.getpass("%s: " % label).strip().strip('"').strip("'").strip()
        if not key:
            print("Nothing was pasted. Copy the key again (the copy icon next to it), then paste here.\n")
            continue
        if not rx.match(key):
            print("That doesn't look like a %s (%s; you pasted %d characters).\n"
                  "Copy it again from where you created it and paste it here.\n" % (label, hint, len(key)))
            continue
        break
    else:
        sys.exit("\nNo key saved. Run the command again when you have the key copied.")
    write_key(name, key)
    print("\nSaved %s ending in ...%s to .env (only your user account can read it)." % (name, key[-4:]))
    if which != "youtube":
        print("Done. Go back to Claude and say: done")
        return
    print("Asking YouTube whether the key works (uses 1 of your 10,000 free daily units)...")
    os.environ[name] = key
    sys.path.insert(0, ROOT)
    import doctor
    from engine.providers import yt
    yt.API_KEY = key
    ok, detail = doctor.live_key_check(yt)
    if ok:
        print("\nIt works. YouTube accepted the key.\nGo back to Claude and say: done")
    else:
        print("\nYouTube did not accept it yet: %s" % detail)
        print("A brand-new key can take up to five minutes to start working. If it still fails after that,\n"
              "go back to Claude, say what this line says, and it will walk you through the fix.")


if __name__ == "__main__":
    main()
