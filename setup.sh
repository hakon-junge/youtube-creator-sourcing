#!/usr/bin/env bash
# One-time setup: local Python environment, two packages, and an empty .env.
set -e
cd "$(dirname "$0")"
command -v python3 >/dev/null || { echo "python3 not found - install Python 3.9 or newer first"; exit 1; }
[ -d .venv ] || python3 -m venv .venv
.venv/bin/pip -q --disable-pip-version-check install -r requirements.txt
chmod +x run_brand.sh setup.sh scripts/*.sh 2>/dev/null || true   # a ZIP download can drop the executable bit
[ -f .env ] || { cp .env.example .env; chmod 600 .env; echo "created .env - paste your keys into it"; }
mkdir -p state out crm
echo "setup done. Next: .venv/bin/python doctor.py"
