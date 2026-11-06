#!/bin/bash
set -euo pipefail
cd -- "$(dirname -- "$0")"

PYTHON_BIN="${PYTHON_BIN:-python3}"
if [ ! -d .venv ]; then
  "$PYTHON_BIN" -m venv .venv
fi
if [ "${INSTALL_DEPS:-0}" = "1" ] || ! .venv/bin/python -c 'import fastapi, uvicorn, playwright, pydantic' >/dev/null 2>&1; then
  .venv/bin/python -m pip install -r requirements.txt
fi
if [ ! -f config.json ]; then
  cp config.example.json config.json
  chmod 600 config.json
fi
export CHROME_HEADLESS="${CHROME_HEADLESS:-1}"
echo "本地控制台：http://127.0.0.1:8765（按 Ctrl+C 停止）"
exec .venv/bin/python app.py
