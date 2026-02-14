# Деплой VetRecorder на свой сервер (VPS)

Пошаговая установка на арендованный Linux-сервер.

---

## 1. Подготовка сервера

SSH на сервер:

```bash
ssh user@your-server-ip
```

Установить Python 3.11, PostgreSQL (если нужна), git:

```bash
# Ubuntu/Debian
sudo apt update
sudo apt install -y python3.11 python3.11-venv python3-pip git nginx

# PostgreSQL (если используете свою БД на сервере)
sudo apt install -y postgresql postgresql-contrib
```

---

## 2. Клонирование и установка

```bash
cd /opt   # или /home/user
git clone https://github.com/Pilotochnik/vetrecorder-.git
cd vetrecorder-
```

Создать `.env`:

```bash
cp env.example .env
nano .env   # заполнить OPENAI_API_KEY, DATABASE_URL, API_TOKEN и т.д.
```

Виртуальное окружение и зависимости:

```bash
python3.11 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

Инициализация БД:

```bash
python init_db.py
```

---

## 3. Проверка локально

```bash
source venv/bin/activate
python app.py &
python bot.py &
curl http://127.0.0.1:5000
```

Остановить процессы (Ctrl+C или kill) и настроить systemd.

---

## 4. Systemd — автозапуск

Создать `/etc/systemd/system/vetrecorder-web.service`:

```ini
[Unit]
Description=VetRecorder Web (Flask)
After=network.target

[Service]
User=www-data
Group=www-data
WorkingDirectory=/opt/vetrecorder--
Environment="PATH=/opt/vetrecorder-/venv/bin"
ExecStart=/opt/vetrecorder-/venv/bin/python app.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Создать `/etc/systemd/system/vetrecorder-bot.service`:

```ini
[Unit]
Description=VetRecorder Telegram Bot
After=network.target

[Service]
User=www-data
Group=www-data
WorkingDirectory=/opt/vetrecorder--
Environment="PATH=/opt/vetrecorder-/venv/bin"
ExecStart=/opt/vetrecorder-/venv/bin/python bot.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Или использовать Gunicorn для веба:

```ini
ExecStart=/opt/vetrecorder-/venv/bin/gunicorn --bind 0.0.0.0:5000 --workers 2 --timeout 120 app:app
```

Включить и запустить:

```bash
sudo chown -R www-data:www-data /opt/vetrecorder-
sudo systemctl daemon-reload
sudo systemctl enable vetrecorder-web vetrecorder-bot
sudo systemctl start vetrecorder-web vetrecorder-bot
sudo systemctl status vetrecorder-web vetrecorder-bot
```

---

## 5. Nginx — прокси и HTTPS

Создать `/etc/nginx/sites-available/vetrecorder`:

```nginx
server {
    listen 80;
    server_name your-domain.com;
    
    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 120;
    }
}
```

Активировать:

```bash
sudo ln -s /etc/nginx/sites-available/vetrecorder /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

HTTPS через Let's Encrypt:

```bash
sudo apt install certbot python3-certbot-nginx
sudo certbot --nginx -d your-domain.com
```

---

## 6. Обновление проекта

```bash
cd /opt/vetrecorder-
git pull
source venv/bin/activate
pip install -r requirements.txt
sudo systemctl restart vetrecorder-web vetrecorder-bot
```

---

## 7. Переменные окружения (.env)

| Переменная     | Описание                    |
|----------------|-----------------------------|
| OPENAI_API_KEY | Ключ OpenAI                 |
| DATABASE_URL   | postgresql://... или sqlite+aiosqlite:///vetrecorder.db |
| API_TOKEN      | Токен бота @vetera_ai_bot   |
| BOT_USERNAME   | vetera_ai_bot               |
| SECRET_KEY     | Случайная строка для Flask  |
| PORT           | 5000 (если запускаете app.py напрямую) |

---

## 8. Полезные команды

```bash
# Логи
sudo journalctl -u vetrecorder-web -f
sudo journalctl -u vetrecorder-bot -f

# Рестарт
sudo systemctl restart vetrecorder-web vetrecorder-bot
```
