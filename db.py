from config import Config
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base

# DATABASE_URL: postgresql:// -> postgresql+asyncpg:// (Render/Railway дают postgresql://)
_db_url = (Config.DATABASE_URL or "").strip() or "sqlite+aiosqlite:///vetrecorder.db"
if _db_url.startswith("postgresql://") and not _db_url.startswith("postgresql+asyncpg"):
    _db_url = _db_url.replace("postgresql://", "postgresql+asyncpg://", 1)

# connect_args только для PostgreSQL (SQLite не поддерживает server_settings)
_engine_kw = {
    "pool_size": Config.DB_POOL_SIZE,
    "max_overflow": Config.DB_MAX_OVERFLOW,
    "pool_pre_ping": False,
    "pool_recycle": Config.DB_POOL_RECYCLE,
    "pool_reset_on_return": "commit",
}
if "postgresql" in _db_url or "asyncpg" in _db_url:
    _engine_kw["connect_args"] = {"server_settings": {"application_name": "vet_voice_mvp"}}

engine = create_async_engine(_db_url, echo=False, **_engine_kw)

# Используем async_sessionmaker вместо sessionmaker для async
SessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False
)
Base = declarative_base()
