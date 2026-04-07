#!/usr/bin/env bash
# Собрать чистую папку проекта для передачи (без .git, без .env, без кэшей).
# По умолчанию: ../Psy for IT BOT-YYYYMMDD рядом с каталогом проекта (удобно для Windows-получателя).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PARENT="$(dirname "$ROOT")"
STAMP="$(date +%Y%m%d)"
DEFAULT_DEST="${PARENT}/Psy for IT BOT-${STAMP}"
DEST="${1:-$DEFAULT_DEST}"

EXCLUDES=(
  '.git'
  '.env'
  '.cursor'
  '__pycache__'
  '.pytest_cache'
  '.venv'
  'venv'
  '.mypy_cache'
  '.ruff_cache'
)

copy_with_rsync() {
  local args=(-a)
  local ex
  for ex in "${EXCLUDES[@]}"; do
    args+=(--exclude="$ex")
  done
  mkdir -p "$DEST"
  rsync "${args[@]}" "$ROOT/" "$DEST/"
}

copy_with_tar() {
  mkdir -p "$DEST"
  local tar_args=(-cf -)
  local ex
  for ex in "${EXCLUDES[@]}"; do
    tar_args+=(--exclude="$ex")
  done
  tar_args+=(-C "$ROOT" .)
  tar "${tar_args[@]}" | tar -xf - -C "$DEST"
}

if command -v rsync >/dev/null 2>&1; then
  copy_with_rsync
else
  echo "rsync не найден, используется tar (исключения те же)" >&2
  copy_with_tar
fi

if [[ ! -f "$ROOT/docs/START_HERE_RECIPIENT.md" ]]; then
  echo "Ошибка: нет файла docs/START_HERE_RECIPIENT.md" >&2
  exit 1
fi
cp -f "$ROOT/docs/START_HERE_RECIPIENT.md" "$DEST/ЧИТАТЬ_СНАЧАЛА.md"

echo "OK: $DEST"
echo "Создайте .env из .env.example, заполните BOT_TOKEN и OWNER_TELEGRAM_IDS. Не коммитьте токен."
