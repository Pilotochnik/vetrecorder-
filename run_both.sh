#!/bin/bash
# VetRecorder — запуск веб и бота (Linux)
cd "$(dirname "$0")"
source venv/bin/activate
python app.py &
APP_PID=$!
python bot.py &
BOT_PID=$!
echo "Flask PID: $APP_PID, Bot PID: $BOT_PID"
echo "Веб: http://127.0.0.1:5000"
wait
