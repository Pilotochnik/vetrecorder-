"""Сервис для работы с файлами"""
import os
import logging
from werkzeug.utils import secure_filename
from config import Config

logger = logging.getLogger(__name__)

class FileService:
    """Сервис для валидации и обработки файлов"""
    
    @staticmethod
    def is_allowed_file(filename: str) -> bool:
        """Проверка разрешенного расширения файла"""
        return '.' in filename and filename.rsplit('.', 1)[1].lower() in Config.ALLOWED_EXTENSIONS
    
    @staticmethod
    def validate_file(file):
        # Returns: (is_valid: bool, error_message: str)
        """
        Валидация загружаемого файла
        
        Returns:
            (is_valid, error_message)
        """
        if not file or file.filename == '':
            return False, 'Файл не выбран'
        
        if not FileService.is_allowed_file(file.filename):
            return False, f'Неподдерживаемый формат файла. Разрешены: {", ".join(Config.ALLOWED_EXTENSIONS)}'
        
        return True, ''
    
    @staticmethod
    def validate_file_size(filepath: str):
        # Returns: (is_valid: bool, error_message: str)
        """
        Проверка размера файла
        
        Returns:
            (is_valid, error_message)
        """
        if not os.path.exists(filepath):
            return False, 'Файл не найден'
        
        file_size = os.path.getsize(filepath)
        if file_size > Config.MAX_FILE_SIZE:
            return False, f'Файл слишком большой (максимум {Config.MAX_FILE_SIZE // (1024*1024)} МБ)'
        
        return True, ''
    
    @staticmethod
    def save_uploaded_file(file, upload_folder: str = None) -> str:
        """
        Сохранение загруженного файла
        
        Returns:
            Путь к сохраненному файлу
        """
        folder = upload_folder or Config.UPLOAD_FOLDER
        os.makedirs(folder, exist_ok=True)
        
        filename = secure_filename(file.filename)
        filepath = os.path.join(folder, filename)
        file.save(filepath)
        
        logger.info(f"Файл сохранен: {filepath}")
        return filepath
    
    @staticmethod
    def cleanup_file(filepath: str):
        """Удаление временного файла"""
        if filepath and os.path.exists(filepath):
            try:
                os.remove(filepath)
                logger.info(f"Временный файл удален: {filepath}")
            except Exception as e:
                logger.warning(f"Не удалось удалить файл {filepath}: {e}")
