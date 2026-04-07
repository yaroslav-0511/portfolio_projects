#!/usr/bin/env bash
# Собрать архив проекта для передачи заказчику (без Git-истории и без .env).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
NAME="$(basename "$ROOT")"
PARENT="$(dirname "$ROOT")"
STAMP="$(date +%Y%m%d)"
DEFAULT_OUT="${PARENT}/${NAME}-handover-${STAMP}.tar.gz"
OUT="${1:-$DEFAULT_OUT}"

cd "$PARENT"
tar -czf "$OUT" \
  --exclude="${NAME}/.git" \
  --exclude="${NAME}/.env" \
  --exclude="${NAME}/__pycache__" \
  --exclude="${NAME}/.pytest_cache" \
  --exclude="${NAME}/.venv" \
  --exclude="${NAME}/venv" \
  --exclude="${NAME}/.mypy_cache" \
  --exclude="${NAME}/.ruff_cache" \
  "$NAME"

echo "OK: $OUT"
