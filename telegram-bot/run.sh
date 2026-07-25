#!/usr/bin/env bash
# Launch the SiteMind Telegram field bot. Run from anywhere; it cd's to telegram-bot/.
set -euo pipefail

cd "$(dirname "$0")"

export PATH="$HOME/.local/bin:$PATH"

if [ ! -d ".venv" ]; then
  ~/.local/bin/python3.12 -m venv .venv
fi
# shellcheck disable=SC1091
source .venv/bin/activate
python -m pip install -q --disable-pip-version-check -r requirements.txt

exec .venv/bin/python bot.py
