"""Env loading and a small HTTP helper shared by the providers. Standard library only."""
import json
import os
import time
import urllib.error
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
BROWSER_UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"
SLEEP = 1.2  # seconds between keyless calls; the rate-limit courtesy, do not remove
_last = [0.0]
_env = {}


def env(key):
    if not _env:
        p = os.path.join(ROOT, ".env")
        if os.path.exists(p):
            for line in open(p):
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    _env[k.strip()] = v.strip().strip('"').strip("'")
        _env.setdefault("_loaded", "1")
    return os.environ.get(key) or _env.get(key) or ""


def pace():
    wait = SLEEP - (time.time() - _last[0])
    if wait > 0:
        time.sleep(wait)
    _last[0] = time.time()


def call(url, headers=None, body=None, timeout=60, raw=False):
    """Returns (status, json-or-text). Network and HTTP failures never raise."""
    data = json.dumps(body).encode() if body is not None else None
    h = {"User-Agent": BROWSER_UA, "Accept": "*/*" if raw else "application/json"}
    h.update(headers or {})
    if data:
        h["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=h)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            txt = r.read().decode("utf-8", "replace")
            return r.status, (txt if raw else json.loads(txt or "{}"))
    except urllib.error.HTTPError as e:
        return e.code, ("" if raw else {"_error": e.read().decode("utf-8", "replace")[:300]})
    except Exception as e:  # timeouts, DNS, bad JSON
        return 0, ("" if raw else {"_error": str(e)[:300]})
