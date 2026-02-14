"""Модуль для работы с Telegram авторизацией и отправкой сообщений"""
import os
import hmac
import hashlib
import time
import logging
from typing import Optional, Dict
import httpx
from dotenv import load_dotenv

load_dotenv()
API_TOKEN = os.getenv("API_TOKEN")
BOT_USERNAME = os.getenv("BOT_USERNAME", "vetera_ai_bot")  # Имя бота без @

def verify_telegram_auth(auth_data: Dict[str, str]) -> Optional[Dict]:
    """Проверка данных авторизации Telegram"""
    try:
        # Получаем hash из данных
        received_hash = auth_data.get('hash')
        if not received_hash:
            return None
        
        # Удаляем hash из данных для проверки
        auth_data_copy = {k: v for k, v in auth_data.items() if k != 'hash'}
        
        # Сортируем данные по ключам
        data_check_string = '\n'.join(f"{k}={v}" for k, v in sorted(auth_data_copy.items()))
        
        # Создаем секретный ключ
        secret_key = hashlib.sha256(API_TOKEN.encode()).digest()
        
        # Вычисляем hash
        calculated_hash = hmac.new(
            secret_key,
            data_check_string.encode(),
            hashlib.sha256
        ).hexdigest()
        
        # Проверяем hash
        if calculated_hash != received_hash:
            logging.warning("Неверный hash при проверке Telegram авторизации")
            return None
        
        # Проверяем время (данные не должны быть старше 24 часов)
        auth_date = int(auth_data.get('auth_date', 0))
        if time.time() - auth_date > 86400:
            logging.warning("Данные авторизации устарели")
            return None
        
        return {
            'id': int(auth_data.get('id')),
            'first_name': auth_data.get('first_name', ''),
            'last_name': auth_data.get('last_name', ''),
            'username': auth_data.get('username', ''),
            'photo_url': auth_data.get('photo_url', ''),
        }
    except Exception as e:
        logging.error(f"Ошибка при проверке Telegram авторизации: {e}")
        return None

async def send_message_to_telegram(user_id: int, text: str, files: Optional[Dict[str, str]] = None) -> bool:
    """Отправка сообщения пользователю в Telegram"""
    try:
        url = f"https://api.telegram.org/bot{API_TOKEN}/sendMessage"
        
        payload = {
            'chat_id': user_id,
            'text': text,
            'parse_mode': 'HTML'
        }
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(url, json=payload)
            response.raise_for_status()
            
            # Если есть файлы, отправляем их
            if files:
                if files.get('txt'):
                    await send_document_to_telegram(user_id, files['txt'], 'Текстовая версия')
                if files.get('docx'):
                    await send_document_to_telegram(user_id, files['docx'], 'Документ Word')
            
            return True
    except Exception as e:
        logging.error(f"Ошибка при отправке сообщения в Telegram: {e}")
        return False

async def send_document_to_telegram(user_id: int, file_path: str, caption: str = "") -> bool:
    """Отправка документа пользователю в Telegram"""
    try:
        if not os.path.exists(file_path):
            logging.error(f"Файл не найден: {file_path}")
            return False
            
        url = f"https://api.telegram.org/bot{API_TOKEN}/sendDocument"
        
        with open(file_path, 'rb') as file:
            file_content = file.read()
            files = {'document': (os.path.basename(file_path), file_content)}
            data = {
                'chat_id': user_id,
                'caption': caption
            }
            
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(url, data=data, files=files)
                response.raise_for_status()
                return True
    except Exception as e:
        logging.error(f"Ошибка при отправке документа в Telegram: {e}")
        return False

def get_telegram_login_widget_script(bot_username: str = None) -> str:
    """Возвращает скрипт для Telegram Login Widget"""
    username = bot_username or BOT_USERNAME
    if not username:
        logging.warning("BOT_USERNAME не установлен, Telegram Login Widget не будет работать")
        return ""
    
    return f"""
    <script async src="https://telegram.org/js/telegram-widget.js?22" 
            data-telegram-login="{username}" 
            data-size="large" 
            data-onauth="onTelegramAuth(user)" 
            data-request-access="write"></script>
    """
