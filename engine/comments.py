"""Audience score: who comments, what they say, and whether they look real.

Two halves, both shown as counts so the score can be audited:
  texture     questions and specific comments vs generic praise and emoji-only
  commenters  the accounts behind the comments: how many are brand-new (looked up in phase2)
Commenters are a proxy for the audience. Viewers who never comment are not visible to anyone.
An account with nothing posted is common among real viewers, so that alone is not a bot signal; the
follow-farm pattern (follows many, followed by almost nobody, nothing posted) is.
"""
import re
from collections import Counter

from . import filters

GENERIC_RX = re.compile(r"^(so |soo+ |such a |very |too )?(cute|adorable|love (this|it|him|her)|aw+|omg|beautiful|gorgeous|amazing|wow|nice|great|lol|haha+|first|same|yes+|no+|stop it|good (boy|girl))\W*$", re.I)
QUESTION_RX = re.compile(r"\?|^(may i|anyone know|is there|how|what|where|which|when|why|can|could|does|do you|did you|is it|are they|would you|any (tips|advice))\b", re.I)
WORD_RX = re.compile(r"[A-Za-zÀ-ÿ']+")


def classify(text):
    words = WORD_RX.findall(text or "")
    if not words:
        return "emoji"
    if QUESTION_RX.search(text.strip()):
        return "question"
    if len(words) <= 3 or GENERIC_RX.match(text.strip()):
        return "generic"
    return "specific" if len(words) >= 6 else "short"


def texture(rows):
    kinds = Counter(classify(r["text"]) for r in rows)
    n = len(rows) or 1
    dup = len(rows) - len({r["text"].strip().lower() for r in rows})
    return {
        "n": len(rows), "question": kinds["question"], "specific": kinds["specific"], "short": kinds["short"],
        "generic": kinds["generic"], "emoji": kinds["emoji"], "duplicates": dup,
        "creator_liked": sum(1 for r in rows if r.get("creator_liked")),
        "substantive_share": round((kinds["question"] + kinds["specific"]) / n, 2),
    }


def score(cfg, rows, commenters_summary, buyer_rx=None):
    """0-100. Substantive comments carry half, real commenters a third, market language the rest."""
    tx = texture(rows)
    for r in rows:  # comments carry no language tag
        if "lang" not in r:
            r["lang"] = filters.detect_lang(r["text"])
    langs = Counter(r.get("lang") for r in rows if r.get("lang") and r.get("lang") != "un")
    market = sum(v for k, v in langs.items() if k in cfg["geo"]["market_langs"])
    lang_share = market / (sum(langs.values()) or 1)
    blob = " ".join(r["text"] for r in rows)
    home, out = filters.markers(cfg, blob)
    buyers = sum(1 for r in rows if buyer_rx and buyer_rx.search(r["text"]))
    est = commenters_summary["established_share"] if commenters_summary and commenters_summary["profiled"] else 0.5
    n = tx["n"] or 1
    # uncalibrated weights: substantive 40, buyer-like 20, real commenters 20, market language 10, creator engages 10
    s = 40 * min(tx["substantive_share"] / 0.8, 1.0) + 20 * min((buyers / n) / 0.3, 1.0) + 20 * est + 10 * lang_share
    if any("creator_liked" in r for r in rows):
        s += 10 * min((tx["creator_liked"] / n) / 0.3, 1.0)
    else:  # not visible on this platform: scale the other four parts to 100
        s = s / 0.9
    return {
        "score": int(round(s)), "texture": tx, "commenters": commenters_summary,
        "comment_langs": dict(langs.most_common(4)), "market_lang_share": round(lang_share, 2),
        "home_markers": home, "out_markers": out, "buyer_comments": buyers,
    }
