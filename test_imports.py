"""Тестовый скрипт для проверки импортов"""
import sys

def test_imports():
    """Проверка всех импортов"""
    errors = []
    
    try:
        print("Проверка config...")
        from config import Config
        print("✓ config.py")
    except Exception as e:
        errors.append(f"config.py: {e}")
        print(f"✗ config.py: {e}")
    
    try:
        print("Проверка services...")
        from services.gpt_service import GPTService
        from services.transcribe_service import TranscribeService
        from services.file_service import FileService
        from services.async_helper import run_async
        print("✓ services")
    except Exception as e:
        errors.append(f"services: {e}")
        print(f"✗ services: {e}")
    
    try:
        print("Проверка utils...")
        from utils.rate_limit import rate_limiter
        print("✓ utils")
    except Exception as e:
        errors.append(f"utils: {e}")
        print(f"✗ utils: {e}")
    
    try:
        print("Проверка основных модулей...")
        from crud import save_intake, get_user_intakes, get_intake_by_id
        from user_crud import get_user_by_session_id, link_session_to_telegram
        from auth_codes import verify_auth_code
        from telegram_auth import send_message_to_telegram
        from save_results import save_to_files
        print("✓ основные модули")
    except Exception as e:
        errors.append(f"основные модули: {e}")
        print(f"✗ основные модули: {e}")
    
    try:
        print("Проверка Flask...")
        from flask import Flask
        print("✓ Flask")
    except Exception as e:
        errors.append(f"Flask: {e}")
        print(f"✗ Flask: {e}")
    
    try:
        print("Проверка app.py...")
        # Не импортируем app.py полностью, так как он может запустить сервер
        import importlib.util
        spec = importlib.util.spec_from_file_location("app", "app.py")
        if spec and spec.loader:
            print("✓ app.py (структура)")
    except Exception as e:
        errors.append(f"app.py: {e}")
        print(f"✗ app.py: {e}")
    
    if errors:
        print("\n" + "="*50)
        print("НАЙДЕНЫ ОШИБКИ:")
        for error in errors:
            print(f"  - {error}")
        return False
    else:
        print("\n" + "="*50)
        print("✓ ВСЕ ИМПОРТЫ УСПЕШНЫ!")
        return True

if __name__ == "__main__":
    success = test_imports()
    sys.exit(0 if success else 1)
