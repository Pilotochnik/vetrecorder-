"""Сервис для транскрибации аудио"""
import os
import logging
import httpx
import openai
from config import Config

logger = logging.getLogger(__name__)

class TranscribeService:
    """Сервис для транскрибации аудио через OpenAI Whisper"""
    
    @staticmethod
    def transcribe(audio_path: str) -> str:
        """
        Транскрибация аудио файла
        
        Args:
            audio_path: Путь к аудио файлу
            
        Returns:
            Транскрибированный текст
            
        Raises:
            FileNotFoundError: Если файл не найден
            ValueError: Если API ключ не установлен
            Exception: При ошибках API
        """
        if not Config.OPENAI_API_KEY:
            raise ValueError("OPENAI_API_KEY не установлен в переменных окружения")
        
        logger.info(f"Начало транскрибации файла: {audio_path}")
        
        if not os.path.exists(audio_path):
            raise FileNotFoundError(f"Файл не найден: {audio_path}")
        
        file_size = os.path.getsize(audio_path)
        logger.info(f"Размер файла для транскрибации: {file_size} байт")
        
        # Создаем httpx.Client явно без прокси
        logger.info("Подключение к OpenAI API")
        http_client = httpx.Client(
            timeout=Config.GPT_TIMEOUT,
            follow_redirects=True
        )
        
        try:
            # Создаем OpenAI клиент
            client = openai.OpenAI(
                api_key=Config.OPENAI_API_KEY,
                http_client=http_client,
                timeout=Config.GPT_TIMEOUT,
                max_retries=Config.GPT_MAX_RETRIES
            )
            
            with open(audio_path, "rb") as audio_file:
                transcript = client.audio.transcriptions.create(
                    model=Config.OPENAI_WHISPER_MODEL,
                    file=audio_file
                )
            
            result_text = transcript.text
            logger.info(f"Транскрибация завершена. Длина текста: {len(result_text)} символов")
            return result_text
        finally:
            http_client.close()
    
    @staticmethod
    def transcribe_with_fallback(audio_path: str, preliminary_transcript: str = None) -> str:
        """
        Транскрибация с использованием предварительной транскрипции если доступна
        
        Args:
            audio_path: Путь к аудио файлу
            preliminary_transcript: Предварительная транскрипция из браузера
            
        Returns:
            Транскрибированный текст
        """
        if preliminary_transcript and len(preliminary_transcript.strip()) > 10:
            logger.info(f"Используется предварительная транскрипция (длина: {len(preliminary_transcript)} символов)")
            try:
                # Пытаемся дополнить через OpenAI для точности
                openai_transcript = TranscribeService.transcribe(audio_path)
                # Используем более длинный вариант
                return openai_transcript if len(openai_transcript) > len(preliminary_transcript) else preliminary_transcript
            except Exception as e:
                logger.warning(f"Не удалось дополнить через OpenAI, используем предварительную: {e}")
                return preliminary_transcript
        else:
            # Полная транскрибация через OpenAI
            return TranscribeService.transcribe(audio_path)
