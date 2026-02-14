@echo off
cd /d "%~dp0"
echo === VetRecorder: Flask + Telegram-бот ===
echo.
echo [1/2] Запуск Flask...
start "VetRecorder Flask" cmd /k "cd /d "%~dp0" && py app.py"
timeout /t 3 /nobreak >nul
echo [2/2] Запуск Telegram-бота...
start "VetRecorder Bot" cmd /k "cd /d "%~dp0" && py bot.py"
echo.
echo Готово. Веб: http://127.0.0.1:5000
echo Бот: /auth в @vetera_ai_bot
echo.
pause
