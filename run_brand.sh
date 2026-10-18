#!/usr/bin/env bash
# One brand, stages 1 to 4: discovery, free gates, capped comment check, handoff.
#   ./run_brand.sh <slug>           channels seen in earlier runs are skipped (they cost nothing)
#   ./run_brand.sh <slug> --fresh   re-read every channel, e.g. the first run after adding an API key
set -eo pipefail
cd "$(dirname "$0")"
B=$1; PY=.venv/bin/python; FRESH=""; [ "$2" = "--fresh" ] && FRESH="--no-state"
[ -n "$B" ] || { echo "usage: ./run_brand.sh <slug> [--fresh]"; exit 1; }
[ -f config/$B.yml ] || { echo "no config/$B.yml - run new_brand.py first"; exit 1; }
if grep -n "TODO" config/$B.yml | grep -v "^[0-9]*:#"; then echo "resolve the TODOs above in config/$B.yml first"; exit 1; fi
export RUN_TAG="$B-$(date +%s)"; export YT_RUN_TAG="$RUN_TAG"   # every phase of this run shares one quota budget
echo "== plan";    $PY phase1.py --brand $B --dry-run $FRESH
echo "== phase1";  $PY phase1.py --brand $B $FRESH 2>&1 | grep -v Deprecated
echo "== phase2";  $PY phase2.py --brand $B 2>&1 | grep -v Deprecated
echo "== phase3";  $PY phase3.py --brand $B
[ -f state/$B.calibrated ] || echo "FIRST RUN for $B: after vetting (Stage 5), build the calibration page with calibrate.py and review it before relying on the results."
