#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

if [[ ! -f requirement.txt ]]; then
  echo "requirement.txt not found in $ROOT" >&2
  exit 1
fi

# Pick a Python that actually runs (Windows Git Bash: `python` is often the useless Store stub; use `py -3`)
pick_python() {
  if [[ -n "${PYTHON:-}" ]]; then
    if "$PYTHON" -c "import sys" &>/dev/null; then
      echo "$PYTHON"
      return 0
    fi
    echo "PYTHON is set but not runnable: $PYTHON" >&2
    return 1
  fi
  for c in python3 python; do
    if command -v "$c" &>/dev/null && "$c" -c "import sys" &>/dev/null; then
      echo "$c"
      return 0
    fi
  done
  if command -v py &>/dev/null; then
    # Windows Python launcher
    if py -3 -c "import sys" &>/dev/null; then
      echo "py -3"
      return 0
    fi
    if py -c "import sys" &>/dev/null; then
      echo "py"
      return 0
    fi
  fi
  echo "No usable Python found." >&2
  echo "  • Install https://www.python.org/downloads/ and tick \"Add python.exe to PATH\" and \"py launcher\"." >&2
  echo "  • Or set PYTHON to your python.exe, e.g. export PYTHON=\"/c/Users/you/AppData/Local/Programs/Python/Python312/python.exe\"" >&2
  return 1
}

PY_LINE="$(pick_python)" || exit 1
# shellcheck disable=SC2206
PY_CMD=( $PY_LINE )

if [[ ! -d .venv ]]; then
  echo "Creating .venv with: ${PY_CMD[*]} ..."
  "${PY_CMD[@]}" -m venv .venv
fi

activate_venv() {
  if [[ -f .venv/Scripts/activate ]]; then
    # shellcheck source=/dev/null
    source .venv/Scripts/activate
  elif [[ -f .venv/bin/activate ]]; then
    # shellcheck source=/dev/null
    source .venv/bin/activate
  else
    echo ".venv exists but has no activate script — remove .venv and run ./setup.sh again" >&2
    exit 1
  fi
}

activate_venv

python -m pip install --upgrade pip
python -m pip install -r requirement.txt

if [[ ! -f .env ]]; then
  if [[ -f .env.example ]]; then
    cp .env.example .env
    echo "Created .env from .env.example — edit it and set TELEGRAM_BOT_TOKEN."
  else
    echo "TELEGRAM_BOT_TOKEN=" > .env
    echo "TELEGRAM_ADMIN_IDS=" >> .env
    echo "Created empty .env — add your secrets."
  fi
fi

chmod +x "$ROOT/run.sh" 2>/dev/null || true

echo "Setup finished. Activate with: source .venv/Scripts/activate   (or .venv/bin/activate on Linux/macOS)"
echo "Or run the bot with: ./run.sh"
