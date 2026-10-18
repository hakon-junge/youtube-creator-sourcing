"""Spend guard. Every paid call asks the ledger first; over a cap the call is refused, never made.

Caps are per run (config `caps`). The day totals are kept in state/ledger.json so cost
projections can be read from real runs later.
"""
import json
import os
from datetime import date, datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PATH = os.path.join(ROOT, "state", "ledger.json")

_run = {"caps": {}, "used": {}, "calls": [], "refused": {}}


class CapReached(Exception):
    pass


def _run_path():
    return os.path.join(ROOT, "state", "run_%s.json" % _run["tag"]) if _run.get("tag") else None


def start_run(caps, tag=None):
    """tag makes the caps hold across the separate phase scripts of one brand run."""
    _run.update(caps=dict(caps or {}), used={}, calls=[], refused={}, tag=tag)
    p = _run_path()
    if p and os.path.exists(p):
        saved = json.load(open(p))
        _run.update(used=saved.get("used", {}), calls=saved.get("calls", []))


def allowed(provider, units=1):
    cap = _run["caps"].get(provider)
    return cap is None or _run["used"].get(provider, 0) + units <= cap


def check(provider, units=1):
    if not allowed(provider, units):
        _run["refused"][provider] = _run["refused"].get(provider, 0) + 1
        raise CapReached("%s cap reached (%s of %s used)" % (provider, _run["used"].get(provider, 0), _run["caps"].get(provider)))


def charge(provider, units, stage, endpoint):
    _run["used"][provider] = _run["used"].get(provider, 0) + (units or 0)
    _run["calls"].append({"t": datetime.utcnow().strftime("%H:%M:%S"), "provider": provider, "units": units, "stage": stage, "endpoint": endpoint})
    d = {}
    if os.path.exists(PATH):
        try:
            d = json.load(open(PATH))
        except ValueError:
            d = {}
    day = d.setdefault(str(date.today()), {})
    day[provider] = day.get(provider, 0) + (units or 0)
    os.makedirs(os.path.dirname(PATH), exist_ok=True)
    json.dump(d, open(PATH, "w"), indent=1)
    if _run_path():
        json.dump({"used": _run["used"], "calls": _run["calls"]}, open(_run_path(), "w"), indent=1)


def summary():
    by_stage = {}
    for c in _run["calls"]:
        k = "%s/%s" % (c["provider"], c["stage"])
        by_stage[k] = by_stage.get(k, 0) + (c["units"] or 0)
    return {"used": dict(_run["used"]), "caps": dict(_run["caps"]), "by_stage": by_stage, "refused": dict(_run["refused"]), "calls": len(_run["calls"])}
