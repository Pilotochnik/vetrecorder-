#!/bin/bash
# VetRecorder — скрипт установки/обновления на сервере
# Использование: ./deploy.sh [install|update]

set -e
cd "$(dirname "$0")"
APP_DIR="$(pwd)"

case "${1:-update}" in
  install)
    echo "=== Установка VetRecorder ==="
    python3 -m venv venv || python3.11 -m venv venv
    source venv/bin/activate
    pip install -r requirements.txt
    if [ ! -f .env ]; then
      cp env.example .env
      echo "Создан .env — заполните переменные: nano .env"
    fi
    python init_db.py
    echo "Установка завершена. Заполните .env и запустите: python app.py && python bot.py"
    ;;
  update)
    echo "=== Обновление VetRecorder ==="
    git pull
    source venv/bin/activate
    pip install -r requirements.txt
    echo "Обновление завершено. Перезапустите сервисы."
    ;;
  *)
    echo "Использование: ./deploy.sh install | update"
    exit 1
    ;;
esac
