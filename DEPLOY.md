# Деплой VetRecorder

**Деплой на свой сервер (VPS):** см. **[DEPLOY_VPS.md](DEPLOY_VPS.md)**

---

## Кратко

1. Клонировать на сервер
2. `cp env.example .env` и заполнить
3. `python -m venv venv && source venv/bin/activate`
4. `pip install -r requirements.txt && python init_db.py`
5. Запустить через systemd (см. DEPLOY_VPS.md) или `python app.py & python bot.py`
6. Nginx + certbot для HTTPS
