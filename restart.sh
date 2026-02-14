#!/bin/bash
# VetRecorder — перезапуск app и bot
cd "$(dirname "$0")"
pkill -f "python app.py" 2>/dev/null
pkill -f "python bot.py" 2>/dev/null
sleep 2
source venv/bin/activate
nohup python app.py > app.log 2>&1 &
nohup python bot.py > bot.log 2>&1 &
sleep 1
echo "Перезапущено: app + bot"
