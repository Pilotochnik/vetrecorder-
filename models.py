from sqlalchemy import Column, Integer, BigInteger, String, DateTime, ForeignKey
from db import Base
import datetime

class User(Base):
    """Пользователь системы"""
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    telegram_id = Column(BigInteger, unique=True, index=True, nullable=True)
    username = Column(String, nullable=True)
    first_name = Column(String, nullable=True)
    last_name = Column(String, nullable=True)
    photo_url = Column(String, nullable=True)
    session_id = Column(String, unique=True, index=True)  # Уникальный ID сессии веб
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    last_login = Column(DateTime, default=datetime.datetime.utcnow)

class Intake(Base):
    __tablename__ = "intakes"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(BigInteger, index=True)   # Telegram ID или hash session_id
    telegram_id = Column(BigInteger, ForeignKey('users.telegram_id'), nullable=True, index=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    result_text = Column(String)
    txt_path = Column(String)
    docx_path = Column(String)

class AuthCode(Base):
    """Коды авторизации для связи веб-сессий с Telegram"""
    __tablename__ = "auth_codes"
    id = Column(Integer, primary_key=True, index=True)
    code = Column(String, unique=True, index=True, nullable=False)
    telegram_id = Column(BigInteger, nullable=False, index=True)
    session_id = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    expires_at = Column(DateTime, nullable=False, index=True)
    used = Column(Integer, default=0)  # 0 = не использован, 1 = использован
