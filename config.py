"""Конфигурация приложения"""
import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    """Базовые настройки приложения"""
    
    # OpenAI
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
    OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-3.5-turbo")
    OPENAI_WHISPER_MODEL = os.getenv("OPENAI_WHISPER_MODEL", "whisper-1")
    
    # Telegram
    API_TOKEN = os.getenv("API_TOKEN")
    BOT_USERNAME = os.getenv("BOT_USERNAME", "vetera_ai_bot")
    
    # Database
    DATABASE_URL = os.getenv("DATABASE_URL")
    
    # Flask
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-key-change-in-production")
    DEBUG = os.getenv("FLASK_DEBUG", "False").lower() == "true"
    PORT = int(os.getenv("PORT", 5000))
    
    # File upload
    UPLOAD_FOLDER = os.getenv("UPLOAD_FOLDER", "uploads")
    ALLOWED_EXTENSIONS = {'mp3', 'wav', 'ogg', 'm4a', 'webm'}
    MAX_FILE_SIZE = 24 * 1024 * 1024  # 24 MB
    
    # Rate limiting
    RATE_LIMIT_ENABLED = os.getenv("RATE_LIMIT_ENABLED", "True").lower() == "true"
    RATE_LIMIT_PER_MINUTE = int(os.getenv("RATE_LIMIT_PER_MINUTE", "10"))
    
    # GPT Settings
    GPT_TEMPERATURE = float(os.getenv("GPT_TEMPERATURE", "0.2"))
    GPT_MAX_TOKENS = int(os.getenv("GPT_MAX_TOKENS", "1500"))
    GPT_TIMEOUT = float(os.getenv("GPT_TIMEOUT", "60.0"))
    GPT_MAX_RETRIES = int(os.getenv("GPT_MAX_RETRIES", "2"))
    
    # Database pool settings
    DB_POOL_SIZE = int(os.getenv("DB_POOL_SIZE", "20"))
    DB_MAX_OVERFLOW = int(os.getenv("DB_MAX_OVERFLOW", "30"))
    DB_POOL_RECYCLE = int(os.getenv("DB_POOL_RECYCLE", "3600"))
    
    @staticmethod
    def init_app(app):
        """Инициализация приложения с конфигурацией"""
        os.makedirs(Config.UPLOAD_FOLDER, exist_ok=True)
