"""Хранение кодов авторизации для связи веб-сессий с Telegram"""
import secrets
import time
import datetime
from typing import Optional, Dict
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession
from db import SessionLocal
from models import AuthCode

async def generate_auth_code(telegram_id: int, session_id: str = None) -> str:
    """Генерация кода авторизации и сохранение в БД"""
    import asyncio
    code = secrets.token_hex(4).upper()  # 8 символов
    expires_at = datetime.datetime.utcnow() + datetime.timedelta(seconds=300)  # 5 минут
    
    max_retries = 3
    for attempt in range(max_retries):
        try:
            async with SessionLocal() as session:
                auth_code = AuthCode(
                    code=code,
                    telegram_id=telegram_id,
                    session_id=session_id,
                    expires_at=expires_at,
                    used=0
                )
                session.add(auth_code)
                await session.commit()
                return code
        except Exception as e:
            error_str = str(e).lower()
            if ("another operation is in progress" in error_str or 
                "connection is closed" in error_str) and attempt < max_retries - 1:
                import logging
                logging.warning(f"Повторная попытка generate_auth_code (попытка {attempt + 1}/{max_retries}): {e}")
                await asyncio.sleep(0.2 * (attempt + 1))
                continue
            raise

async def verify_auth_code(code: str) -> Optional[Dict]:
    """Проверка кода авторизации из БД"""
    import asyncio
    code_upper = code.upper().strip()
    current_time = datetime.datetime.utcnow()
    
    max_retries = 3
    for attempt in range(max_retries):
        try:
            async with SessionLocal() as session:
                # Ищем код
                result = await session.execute(
                    select(AuthCode).where(
                        AuthCode.code == code_upper,
                        AuthCode.used == 0,
                        AuthCode.expires_at > current_time
                    )
                )
                auth_code = result.scalar_one_or_none()
                
                if not auth_code:
                    return None
                
                # Помечаем код как использованный
                auth_code.used = 1
                await session.commit()
                
                return {
                    'telegram_id': auth_code.telegram_id,
                    'session_id': auth_code.session_id,
                    'expires_at': auth_code.expires_at.timestamp(),
                    'created_at': auth_code.created_at.timestamp()
                }
        except Exception as e:
            error_str = str(e).lower()
            if ("another operation is in progress" in error_str or 
                "connection is closed" in error_str) and attempt < max_retries - 1:
                import logging
                logging.warning(f"Повторная попытка проверки кода (попытка {attempt + 1}/{max_retries}): {e}")
                await asyncio.sleep(0.2 * (attempt + 1))
                continue
            import logging
            logging.error(f"Ошибка при проверке кода авторизации: {e}", exc_info=True)
            raise

async def cleanup_expired_codes():
    """Очистка истекших кодов из БД"""
    current_time = datetime.datetime.utcnow()
    
    async with SessionLocal() as session:
        await session.execute(
            delete(AuthCode).where(
                (AuthCode.expires_at < current_time) | (AuthCode.used == 1)
            )
        )
        await session.commit()
