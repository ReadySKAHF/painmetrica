#!/bin/bash
# ─── Painmetrica: деплой / обновление на сервере ─────────────────────────────
set -e

APP_DIR="/var/www/painmetrica"
VENV_DIR="$APP_DIR/venv"

echo "=== [1/5] Pull из Git ==="
cd "$APP_DIR"
git pull origin main

echo "=== [2/5] Зависимости ==="
"$VENV_DIR/bin/pip" install --quiet --upgrade pip
"$VENV_DIR/bin/pip" install --quiet -r "$APP_DIR/requirements.txt"

echo "=== [3/5] Миграции ==="
"$VENV_DIR/bin/python" manage.py migrate --noinput

echo "=== [4/5] Статика ==="
"$VENV_DIR/bin/python" manage.py collectstatic --noinput --clear

echo "=== [5/5] Перезапуск ==="
sudo systemctl restart painmetrica

echo "=== Деплой завершён ==="
