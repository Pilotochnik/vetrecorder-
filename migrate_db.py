"""Миграция БД: добавление колонки telegram_id в таблицу intakes если её нет"""
import asyncio
from sqlalchemy import text
from db import engine

async def migrate():
    """Добавляет колонку telegram_id если её нет"""
    async with engine.begin() as conn:
        # Проверяем, существует ли колонка
        check_query = text("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name='intakes' AND column_name='telegram_id'
        """)
        result = await conn.execute(check_query)
        exists = result.fetchone() is not None
        
        if not exists:
            print("Добавляем колонку telegram_id в таблицу intakes...")
            # Добавляем колонку
            alter_query = text("""
                ALTER TABLE intakes 
                ADD COLUMN telegram_id BIGINT,
                ADD CONSTRAINT fk_intakes_telegram_id 
                FOREIGN KEY (telegram_id) REFERENCES users(telegram_id)
            """)
            await conn.execute(alter_query)
            print("Колонка telegram_id добавлена успешно!")
        else:
            print("Колонка telegram_id уже существует")

if __name__ == "__main__":
    asyncio.run(migrate())
