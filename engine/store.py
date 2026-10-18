"""Local state per brand: seen-store, query log and view snapshots. One SQLite file per brand.

The seen-store makes runs idempotent (a handle rejected last week is not re-paid for this week).
Snapshots record each recent post's views with a date, so a later boost can be compared with what
the post had before it.
"""
import json
import os
import sqlite3
from datetime import datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def now():
    return datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")


def conn(brand):
    os.makedirs(os.path.join(ROOT, "state"), exist_ok=True)
    c = sqlite3.connect(os.path.join(ROOT, "state", "%s.db" % brand))
    c.executescript("""
        create table if not exists seen(handle text primary key, first_seen text, last_seen text, lane text, reason text);
        create table if not exists queries(q text, ts text, hits integer);
        create table if not exists snapshots(video_id text, handle text, ts text, views integer, likes integer, comments integer);
    """)
    return c


def is_seen(c, handle):
    return c.execute("select lane, reason, last_seen from seen where handle=?", (handle,)).fetchone()


def mark_seen(c, handle, lane, reason):
    t = now()
    c.execute("insert into seen values(?,?,?,?,?) on conflict(handle) do update set last_seen=?, lane=?, reason=?",
              (handle, t, t, lane, reason, t, lane, reason))


def log_query(c, q, hits):
    c.execute("insert into queries values(?,?,?)", (q, now(), hits))


def snapshot(c, handle, videos):
    t = now()
    c.executemany("insert into snapshots values(?,?,?,?,?,?)",
                  [(v["id"], handle, t, v.get("views"), v.get("likes"), v.get("comments")) for v in videos])


def dump_json(obj, path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump(obj, f, indent=1, ensure_ascii=False)
