# Запуск Flask и Telegram-бота (два окна)
# Использование: .\run_both.ps1

$projectDir = Split-Path -Parent $MyInvocation.MyCommand.Path

Write-Host "=== VetRecorder: запуск Flask + Telegram-бот ===" -ForegroundColor Cyan
Write-Host ""

# Проверка API_TOKEN
$envContent = Get-Content "$projectDir\.env" -ErrorAction SilentlyContinue
$hasToken = $envContent | Where-Object { $_ -match "^API_TOKEN=.+" }
if (-not $hasToken) {
    Write-Host "ВНИМАНИЕ: API_TOKEN не найден в .env. Бот не будет работать." -ForegroundColor Yellow
    Write-Host "Добавьте API_TOKEN=ваш_токен_от_BotFather в файл .env" -ForegroundColor Yellow
    Write-Host ""
}

# Запуск Flask в новом окне
Write-Host "[1/2] Открытие окна Flask (app.py) ..." -ForegroundColor Green
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$projectDir'; Write-Host 'Flask (VetRecorder Web)' -ForegroundColor Cyan; py app.py"

Start-Sleep -Seconds 2

# Запуск бота в новом окне
Write-Host "[2/2] Открытие окна Telegram-бота (bot.py) ..." -ForegroundColor Green
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$projectDir'; Write-Host 'Telegram Bot (VetRecorder)' -ForegroundColor Cyan; py bot.py"

Write-Host ""
Write-Host "Готово. Открыто 2 окна:" -ForegroundColor Green
Write-Host "  - Flask: веб http://127.0.0.1:5000" -ForegroundColor White
Write-Host "  - Бот: отправьте /auth в @vetera_ai_bot" -ForegroundColor White
Write-Host ""
Write-Host "Закройте окна PowerShell для остановки процессов." -ForegroundColor Gray
