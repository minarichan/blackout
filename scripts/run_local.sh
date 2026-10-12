#!/usr/bin/env sh
set -eu
root=$(CDPATH= cd -- "$(dirname "$0")/.." && pwd)
(
  cd "$root/backend"
  python -m uvicorn app.main:app --reload --port 8000
) &
(
  cd "$root/frontend"
  npm run dev
) &
wait
