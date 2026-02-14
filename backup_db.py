"""Скрипт для создания бэкапа базы данных"""
import os
import subprocess
import datetime
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    print("Ошибка: DATABASE_URL не установлен в .env")
    exit(1)

# Парсим DATABASE_URL для получения параметров подключения
# Формат: postgresql+asyncpg://user:password@host:port/database
try:
    # Убираем префикс postgresql+asyncpg://
    db_url = DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://")
    
    # Создаем имя файла бэкапа
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    backup_dir = "backups"
    os.makedirs(backup_dir, exist_ok=True)
    backup_file = os.path.join(backup_dir, f"backup_{timestamp}.sql")
    
    print(f"Создание бэкапа базы данных...")
    print(f"Файл: {backup_file}")
    
    # Используем pg_dump для создания бэкапа
    # Для Neon и других облачных БД нужно использовать pg_dump с правильными параметрами
    cmd = [
        "pg_dump",
        db_url,
        "-f", backup_file,
        "--no-owner",
        "--no-acl"
    ]
    
    result = subprocess.run(cmd, capture_output=True, text=True)
    
    if result.returncode == 0:
        file_size = os.path.getsize(backup_file)
        print(f"✓ Бэкап успешно создан!")
        print(f"  Размер файла: {file_size / 1024:.2f} KB")
        print(f"  Путь: {os.path.abspath(backup_file)}")
    else:
        print(f"✗ Ошибка при создании бэкапа:")
        print(result.stderr)
        print("\nПримечание: Для создания бэкапа нужен установленный pg_dump.")
        print("Альтернатива: используйте встроенные инструменты вашего провайдера БД (Neon, Supabase и т.д.)")
        
except Exception as e:
    print(f"Ошибка: {e}")
    print("\nРучной бэкап:")
    print("1. Используйте панель управления вашего провайдера БД")
    print("2. Или используйте pgAdmin/DBeaver для экспорта данных")
    print(f"3. Текущая DATABASE_URL: {DATABASE_URL[:50]}...")
