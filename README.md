# VetRecorder

AI-ассистент для ветеринаров: записывайте приём голосом → получайте готовые SOAP-заметки.

🌐 **Демо:** http://72.56.106.181:5000

[![Python](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/)
[![Flask](https://img.shields.io/badge/Flask-3.x-green.svg)](https://flask.palletsprojects.com/)
[![OpenAI](https://img.shields.io/badge/OpenAI-Whisper%20%2B%20GPT-orange.svg)](https://openai.com/)

---

## Возможности

- **Веб-интерфейс** — запись и загрузка аудио приёма
- **Транскрибация** — OpenAI Whisper
- **Структурирование** — GPT формирует SOAP-формат (жалобы, анамнез, диагноз, назначения)
- **Telegram-бот** — голосовые сообщения, /auth, /history
- **Экспорт** — TXT и DOCX для карты пациента
- **Авторизация** — связка веб ↔ Telegram через код

---

## Быстрый старт

### Локально (Windows)

```bash
git clone https://github.com/Pilotochnik/vetrecorder-.git
cd vetrecorder-

python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt

copy env.example .env
# Заполнить .env: OPENAI_API_KEY, DATABASE_URL, API_TOKEN

python init_db.py
run_both.bat
```

Открыть: http://127.0.0.1:5000

### Локально (Linux / macOS)

```bash
git clone https://github.com/Pilotochnik/vetrecorder-.git
cd vetrecorder-

python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

cp env.example .env
# Заполнить .env

python init_db.py
chmod +x run_both.sh
./run_both.sh
```

---

## Деплой на сервер (VPS)

Подробно: **[DEPLOY_VPS.md](DEPLOY_VPS.md)**

```bash
git clone https://github.com/Pilotochnik/vetrecorder-.git
cd vetrecorder-
./deploy.sh install
# Заполнить .env, настроить systemd
```

---

## Структура проекта

```
vetrecorder-/
├── app.py              # Flask — веб, API
├── bot.py              # Telegram-бот
├── config.py           # Конфигурация
├── db.py               # Async SQLAlchemy
├── models.py           # User, Intake, AuthCode
├── user_crud.py        # CRUD пользователей
├── crud.py             # Intakes
├── auth_codes.py       # Коды авторизации
├── telegram_auth.py    # Отправка в Telegram
├── save_results.py     # TXT / DOCX
├── services/           # GPT, Whisper, File
├── templates/          # HTML
├── utils/              # Rate limit
├── deploy.sh           # Установка на сервер
├── run_both.sh         # Запуск (Linux)
├── run_both.bat        # Запуск (Windows)
├── env.example         # Шаблон переменных
├── DEPLOY_VPS.md       # Инструкция деплоя
└── requirements.txt
```

---

## Переменные окружения

| Переменная     | Описание                    |
|----------------|-----------------------------|
| OPENAI_API_KEY | Ключ OpenAI                 |
| DATABASE_URL   | PostgreSQL или SQLite       |
| API_TOKEN      | Токен Telegram-бота         |
| BOT_USERNAME   | Имя бота                    |
| SECRET_KEY     | Секрет Flask (для прода)    |

Полный список — `env.example`.

---

## Лицензия

MIT
