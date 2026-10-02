#!/usr/bin/env bash
# S.A.R.A launcher — creates venv if needed, installs deps, and starts server.
set -e
cd "$(dirname "$0")"

if [ ! -d ".venv" ]; then
  echo "[S.A.R.A] Creating virtual environment…"
  python3 -m venv .venv
fi

source .venv/bin/activate

echo "[S.A.R.A] Installing dependencies…"
pip install --upgrade pip -q
pip install -r requirements.txt -q

if [ ! -f ".env" ]; then
  echo "[S.A.R.A] No .env found — creating one from .env.example."
  cp .env.example .env
  echo ""
  echo "! Edit .env and add your GEMINI_API_KEY and ELEVENLABS_API_KEY,"
  echo "  then re-run this script."
  echo ""
  exit 1
fi

echo "[S.A.R.A] Starting server on http://localhost:8000 …"
exec python run.py --reload
