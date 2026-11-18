#!/bin/bash
# Jalankan aplikasi Streamlit dengan virtual environment lokal.
# Skrip ini mencari Python 3.10+ karena Scrapling tidak mendukung Python 3.9.
set -euo pipefail
cd "$(dirname "$0")"

is_supported() {
  "$1" -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)' >/dev/null 2>&1
}

find_python() {
  local candidates=()
  # Utamakan interpreter dari venv proyek induk bila tersedia (sudah 3.11).
  if [ -x "../.venv/bin/python" ]; then
    candidates+=("../.venv/bin/python")
  fi
  local name
  for name in python3.13 python3.12 python3.11 python3.10 python3; do
    if command -v "$name" >/dev/null 2>&1; then
      candidates+=("$name")
    fi
  done
  local candidate
  for candidate in "${candidates[@]}"; do
    if is_supported "$candidate"; then
      printf '%s\n' "$candidate"
      return 0
    fi
  done
  return 1
}

if [ -d .venv ] && ! is_supported .venv/bin/python; then
  echo "Virtual environment .venv memakai Python < 3.10; membuat ulang..."
  rm -rf .venv
fi

if [ ! -d .venv ]; then
  PYTHON="$(find_python || true)"
  if [ -z "$PYTHON" ]; then
    cat >&2 <<'MSG'
Python 3.10+ tidak ditemukan.

Pasang Python 3.11/3.12 terlebih dahulu, misalnya:
  brew install python@3.12
atau:
  uv python install 3.12

Lalu jalankan ulang ./run.command
MSG
    exit 1
  fi
  echo "Membuat virtual environment dengan $("$PYTHON" -V 2>&1) ..."
  "$PYTHON" -m venv .venv
fi

if ! .venv/bin/python -c "import streamlit, scrapling, pandas, openpyxl" >/dev/null 2>&1; then
  .venv/bin/python -m pip install --quiet --upgrade pip
  .venv/bin/python -m pip install --quiet -r requirements.txt
fi

exec .venv/bin/streamlit run app.py "$@"
