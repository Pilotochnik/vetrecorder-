import asyncio
from db import engine, Base
import models

async def init_models():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("Таблицы созданы: users, intakes")

if __name__ == "__main__":
    asyncio.run(init_models())
