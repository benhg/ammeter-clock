#!/bin/bash
set -e
cd "$(dirname "$0")/../.."
if ! command -v python3 >/dev/null; then
  echo "Install Python 3 from python.org, then run this launcher again."
  read -r -p "Press Enter to close."
  exit 1
fi
if [ ! -x .venv-clock/bin/python ]; then python3 -m venv .venv-clock; fi
.venv-clock/bin/python -m pip -q install -r tools/clock_setup/requirements.txt
.venv-clock/bin/python tools/clock_setup/app.py
