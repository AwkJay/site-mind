#!/usr/bin/env bash
# Launch the SiteMind Telegram field bot. Run from anywhere; it cd's to telegram-bot/.
set -euo pipefail

cd "$(dirname "$0")"

PY="$(command -v python3.12 || command -v python3.11 || command -v python3)"
if [ ! -d ".venv" ]; then
  "$PY" -m venv .venv
fi
# shellcheck disable=SC1091
source .venv/bin/activate
pip install -q --disable-pip-version-check -r requirements.txt

exec python bot.py
