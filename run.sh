#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

activate_venv() {
  if [[ -f .venv/Scripts/activate ]]; then
    # shellcheck source=/dev/null
    source .venv/Scripts/activate
  elif [[ -f .venv/bin/activate ]]; then
    # shellcheck source=/dev/null
    source .venv/bin/activate
  fi
}

activate_venv

if [[ ! -f .env ]]; then
  echo "Missing .env — run ./setup.sh first or copy .env.example to .env" >&2
  exit 1
fi

case "${1:-bot}" in
  watcher|watch)
    exec python watcher.py
    ;;
  bot|""|m)
    exec python m.py
    ;;
  *)
    echo "Usage: $0 [bot|watcher]" >&2
    echo "  bot      — run m.py (default)" >&2
    echo "  watcher — run watcher.py" >&2
    exit 1
    ;;
esac
