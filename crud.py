from db import SessionLocal
from models import Intake
from sqlalchemy import select
import asyncio

# --- Повторная попытка, если connection closed ---
async def with_retry(func, *args, **kwargs):
    for i in range(2):
        try:
            return await func(*args, **kwargs)
        except Exception as e:
            if "connection is closed" in str(e) and i == 0:
                await asyncio.sleep(0.5)
                continue
            raise

async def save_intake(user_id, result_text, txt_path, docx_path):
    async def inner():
        async with SessionLocal() as session:
            intake = Intake(
                user_id=user_id,
                result_text=result_text,
                txt_path=txt_path,
                docx_path=docx_path
            )
            session.add(intake)
            await session.commit()
    return await with_retry(inner)

async def get_user_intakes(user_id):
    async def inner():
        async with SessionLocal() as session:
            result = await session.execute(
                select(Intake).where(Intake.user_id == user_id)
            )
            return result.scalars().all()
    return await with_retry(inner)

async def get_intake_by_id(intake_id):
    async def inner():
        async with SessionLocal() as session:
            result = await session.execute(
                select(Intake).where(Intake.id == intake_id)
            )
            return result.scalar_one_or_none()
    return await with_retry(inner)
