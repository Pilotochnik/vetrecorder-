"""Сервис для работы с GPT API"""
import logging
import httpx
import openai
from config import Config

logger = logging.getLogger(__name__)

class GPTService:
    """Сервис для структурирования текста через GPT"""
    
    PROMPT_TEMPLATE = (
        "Ты — опытный ветеринарный врач в российской клинике. Пациент уже на приёме и осмотрен, "
        "диагноз формулируется по результатам осмотра и диалога.\n"
        "Тебе нужно:\n"
        "1. Извлечь только фактические 'Жалобы' и 'Анамнез' из разговора.\n"
        "2. Сформулировать предварительный диагноз ('Предварительный диагноз').\n"
        "3. В разделе 'Предварительные назначения' — отвечать для клиента, указывая конкретные препараты "
        "(торговые названия, если возможно), которые часто используются в России, а также зарубежные аналоги, "
        "если применяются. Не используй фразы «необходимо провести осмотр» или «точную дозировку определяет врач» — "
        "ты сам уже врач, дай рекомендации так, как будто ведёшь приём лично. Указывай примерную дозировку, "
        "если это безопасно. Если информации не хватает, напиши конкретно, какие данные ещё нужны.\n"
        "4. В 'Рекомендациях' — советы по уходу, транспорту, профилактике, наблюдению и дальнейшим действиям.\n"
        "Строго структурируй результат так:\n"
        "1. Жалобы: ...\n"
        "2. Анамнез: ...\n"
        "3. Предварительный диагноз: ...\n"
        "4. Предварительные назначения: ...\n"
        "5. Рекомендации: ...\n\n"
        "Текст диалога:\n{text}"
    )
    
    @staticmethod
    def structure_text(dialog_text: str) -> str:
        """
        Структурирование текста через GPT
        
        Args:
            dialog_text: Текст диалога для структурирования
            
        Returns:
            Структурированный текст
            
        Raises:
            ValueError: Если текст слишком короткий
            Exception: При ошибках API
        """
        if not dialog_text or len(dialog_text.strip()) < 10:
            logger.warning("Пустой или слишком короткий текст для структурирования")
            raise ValueError("Текст слишком короткий для анализа.")
        
        prompt = GPTService.PROMPT_TEMPLATE.format(text=dialog_text)
        logger.info(f"Начало структурирования через GPT. Длина текста: {len(dialog_text)} символов")
        
        try:
            # Создаем httpx.Client явно без прокси
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
                
                logger.info("Отправка запроса к OpenAI GPT API...")
                response = client.chat.completions.create(
                    model=Config.OPENAI_MODEL,
                    messages=[
                        {"role": "system", "content": "Ты — опытный ветеринарный врач."},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=Config.GPT_TEMPERATURE,
                    max_tokens=Config.GPT_MAX_TOKENS,
                )
                
                result = response.choices[0].message.content.strip()
                logger.info(f"Структурирование завершено. Длина результата: {len(result)} символов")
                return result
            finally:
                http_client.close()
        
        except openai.RateLimitError as e:
            logger.error(f"Превышен лимит запросов к OpenAI API: {e}")
            raise Exception("Превышен лимит запросов к OpenAI API. Попробуйте позже.")
        except openai.APIConnectionError as e:
            logger.error(f"Ошибка подключения к OpenAI API: {e}")
            raise Exception("Ошибка подключения к OpenAI API. Проверьте интернет-соединение.")
        except openai.APIError as e:
            error_code = getattr(e, 'status_code', None)
            error_message = str(e)
            logger.error(f"Ошибка OpenAI API (код {error_code}): {e}", exc_info=True)
            
            # Обработка ошибки 403 (неподдерживаемый регион)
            if error_code == 403 or 'unsupported_country' in error_message.lower() or 'region' in error_message.lower():
                raise Exception("OpenAI API недоступен в вашем регионе. Используйте VPN или обратитесь к администратору.")
            
            raise Exception(f"Ошибка OpenAI API: {error_message}")
        except Exception as e:
            logger.error(f"Ошибка при структурировании через GPT: {e}", exc_info=True)
            error_str = str(e).lower()
            if 'unsupported_country' in error_str or 'region' in error_str or '403' in error_str:
                raise Exception("OpenAI API недоступен в вашем регионе. Используйте VPN или обратитесь к администратору.")
            raise
