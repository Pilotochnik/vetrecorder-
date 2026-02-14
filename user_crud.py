"""CRUD операции для пользователей"""
from db import SessionLocal
from models import User, Intake
from sqlalchemy import select, update
import asyncio
import datetime
import time

async def get_or_create_user_by_telegram(telegram_data: dict) -> User:
    """Получить или создать пользователя по Telegram данным"""
    max_retries = 3
    for attempt in range(max_retries):
        try:
            async with SessionLocal() as session:
                # Ищем пользователя по telegram_id
                result = await session.execute(
                    select(User).where(User.telegram_id == telegram_data['id'])
                )
                user = result.scalar_one_or_none()
                
                if user:
                    # Обновляем данные
                    user.username = telegram_data.get('username')
                    user.first_name = telegram_data.get('first_name')
                    user.last_name = telegram_data.get('last_name')
                    user.photo_url = telegram_data.get('photo_url')
                    user.last_login = datetime.datetime.utcnow()
                else:
                    # Создаем нового пользователя
                    user = User(
                        telegram_id=telegram_data['id'],
                        username=telegram_data.get('username'),
                        first_name=telegram_data.get('first_name'),
                        last_name=telegram_data.get('last_name'),
                        photo_url=telegram_data.get('photo_url'),
                        session_id=f"tg_{telegram_data['id']}"
                    )
                    session.add(user)
                
                await session.commit()
                await session.refresh(user)
                return user
        except Exception as e:
            error_str = str(e).lower()
            if ("another operation is in progress" in error_str or 
                "connection is closed" in error_str) and attempt < max_retries - 1:
                import logging
                logging.warning(f"Повторная попытка get_or_create_user (попытка {attempt + 1}/{max_retries}): {e}")
                await asyncio.sleep(0.2 * (attempt + 1))
                continue
            raise

async def get_user_by_session_id(session_id: str) -> User:
    """Получить пользователя по session_id"""
    async with SessionLocal() as session:
        result = await session.execute(
            select(User).where(User.session_id == session_id)
        )
        return result.scalar_one_or_none()

async def get_or_create_user_by_session_id(session_id: str) -> User:
    """Получить или создать пользователя по session_id"""
    max_retries = 3
    for attempt in range(max_retries):
        try:
            async with SessionLocal() as session:
                # Ищем пользователя по session_id
                result = await session.execute(
                    select(User).where(User.session_id == session_id)
                )
                user = result.scalar_one_or_none()
                
                if user:
                    # Обновляем last_login
                    user.last_login = datetime.datetime.utcnow()
                    await session.commit()
                    await session.refresh(user)
                    return user
                else:
                    # Создаем нового пользователя
                    user = User(
                        session_id=session_id,
                        created_at=datetime.datetime.utcnow(),
                        last_login=datetime.datetime.utcnow()
                    )
                    session.add(user)
                    await session.commit()
                    await session.refresh(user)
                    return user
        except Exception as e:
            error_str = str(e).lower()
            if ("another operation is in progress" in error_str or 
                "connection is closed" in error_str) and attempt < max_retries - 1:
                import logging
                logging.warning(f"Повторная попытка get_or_create_user_by_session_id (попытка {attempt + 1}/{max_retries}): {e}")
                await asyncio.sleep(0.2 * (attempt + 1))
                continue
            raise

async def link_session_to_telegram(session_id: str, telegram_id: int) -> bool:
    """Связать веб-сессию с Telegram аккаунтом"""
    max_retries = 3
    for attempt in range(max_retries):
        try:
            async with SessionLocal() as db_session:
                # Ищем пользователя по telegram_id
                result = await db_session.execute(
                    select(User).where(User.telegram_id == telegram_id)
                )
                tg_user = result.scalar_one_or_none()
                
                # Ищем пользователя, у которого уже занят этот session_id
                result_session = await db_session.execute(
                    select(User).where(User.session_id == session_id)
                )
                session_user = result_session.scalar_one_or_none()
                
                if session_user and tg_user and session_user.id != tg_user.id:
                    # session_id принадлежит другому (веб-пользователю)
                    # 1) Явный UPDATE — освобождаем session_id до присвоения tg_user
                    new_sid = f"merged_{session_user.id}_{int(time.time())}"
                    await db_session.execute(
                        update(User).where(User.id == session_user.id).values(session_id=new_sid)
                    )
                    await db_session.flush()
                    # 2) Переносим записи к Telegram-пользователю
                    await db_session.execute(
                        update(Intake)
                        .where(Intake.user_id == session_user.id)
                        .values(user_id=tg_user.id, telegram_id=tg_user.telegram_id)
                    )
                    await db_session.flush()
                
                if tg_user:
                    await db_session.execute(
                        update(User).where(User.id == tg_user.id).values(session_id=session_id)
                    )
                    await db_session.commit()
                    return True
                
                # tg_user нет — веб-пользователь связывает сессию с Telegram
                if session_user:
                    # Назначаем telegram_id веб-пользователю (он становится Telegram-пользователем)
                    session_user.telegram_id = telegram_id
                    await db_session.commit()
                    return True
                
                # Ни tg_user, ни session_user — создаем нового
                user = User(
                    telegram_id=telegram_id,
                    session_id=session_id
                )
                db_session.add(user)
                await db_session.commit()
                return True
        except Exception as e:
            error_str = str(e).lower()
            if ("another operation is in progress" in error_str or 
                "connection is closed" in error_str) and attempt < max_retries - 1:
                import logging
                logging.warning(f"Повторная попытка link_session (попытка {attempt + 1}/{max_retries}): {e}")
                await asyncio.sleep(0.2 * (attempt + 1))
                continue
            import logging
            logging.error(f"Ошибка при связывании сессии: {e}", exc_info=True)
            raise
