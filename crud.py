from db import SessionLocal
from models import Intake
from sqlalchemy import select
import asyncio

# --- Повторная попытка, если connection closed или another operation in progress ---
async def with_retry(func, *args, **kwargs):
    max_retries = 3
    for i in range(max_retries):
        try:
            return await func(*args, **kwargs)
        except Exception as e:
            error_str = str(e).lower()
            if ("connection is closed" in error_str or 
                "another operation is in progress" in error_str) and i < max_retries - 1:
                await asyncio.sleep(0.2 * (i + 1))  # Увеличиваем задержку с каждой попыткой
                continue
            raise

async def save_intake(user_id, result_text, txt_path, docx_path, telegram_id=None):
    async def inner():
        async with SessionLocal() as session:
            try:
                import logging
                logging.info(f"💾 Сохранение intake: user_id={user_id}, telegram_id={telegram_id}, text_len={len(result_text) if result_text else 0}")
                intake = Intake(
                    user_id=user_id,
                    telegram_id=telegram_id,
                    result_text=result_text,
                    txt_path=txt_path,
                    docx_path=docx_path
                )
                session.add(intake)
                await session.commit()
                await session.refresh(intake)
                logging.info(f"✅ Intake сохранен: id={intake.id}, user_id={intake.user_id}, telegram_id={intake.telegram_id}")
                return intake.id
            except Exception as e:
                await session.rollback()
                import logging
                logging.error(f"❌ Ошибка сохранения intake: {e}", exc_info=True)
                raise
    return await with_retry(inner)

async def get_user_intakes(user_id, telegram_id=None):
    async def inner():
        async with SessionLocal() as session:
            try:
                import logging
                logging.info(f"🔍 Поиск intakes: user_id={user_id}, telegram_id={telegram_id}")
                # Если есть telegram_id, ищем по нему, иначе по user_id
                if telegram_id:
                    result = await session.execute(
                        select(Intake).where(
                            (Intake.telegram_id == telegram_id) | (Intake.user_id == user_id)
                        ).order_by(Intake.created_at.desc())
                    )
                else:
                    result = await session.execute(
                        select(Intake).where(Intake.user_id == user_id).order_by(Intake.created_at.desc())
                    )
                intakes = result.scalars().all()
                # Преобразуем в список для безопасности
                intakes_list = list(intakes) if intakes else []
                logging.info(f"🔍 Найдено intakes: {len(intakes_list)}")
                if intakes_list:
                    logging.info(f"🔍 Первый intake: id={intakes_list[0].id}, user_id={intakes_list[0].user_id}, telegram_id={intakes_list[0].telegram_id}")
                return intakes_list
            except Exception as e:
                await session.rollback()
                # Возвращаем пустой список вместо ошибки
                import logging
                logging.error(f"❌ Ошибка получения истории для user_id={user_id}, telegram_id={telegram_id}: {e}", exc_info=True)
                return []
    return await with_retry(inner)

async def get_intake_by_id(intake_id):
    async def inner():
        async with SessionLocal() as session:
            result = await session.execute(
                select(Intake).where(Intake.id == intake_id)
            )
            return result.scalar_one_or_none()
    return await with_retry(inner)
