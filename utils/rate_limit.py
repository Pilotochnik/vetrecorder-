"""Rate limiting утилиты"""
import time
from collections import defaultdict
from threading import Lock
from config import Config

class RateLimiter:
    """Простой rate limiter на основе памяти"""
    
    def __init__(self):
        self.requests = defaultdict(list)
        self.lock = Lock()
        self.enabled = Config.RATE_LIMIT_ENABLED
        self.limit = Config.RATE_LIMIT_PER_MINUTE
    
    def is_allowed(self, identifier: str) -> bool:
        """
        Проверка, разрешен ли запрос
        
        Args:
            identifier: Уникальный идентификатор (IP, user_id, etc.)
            
        Returns:
            True если запрос разрешен, False если превышен лимит
        """
        if not self.enabled:
            return True
        
        current_time = time.time()
        
        with self.lock:
            # Удаляем старые запросы (старше минуты)
            self.requests[identifier] = [
                req_time for req_time in self.requests[identifier]
                if current_time - req_time < 60
            ]
            
            # Проверяем лимит
            if len(self.requests[identifier]) >= self.limit:
                return False
            
            # Добавляем текущий запрос
            self.requests[identifier].append(current_time)
            return True
    
    def reset(self, identifier: str):
        """Сброс счетчика для идентификатора"""
        with self.lock:
            if identifier in self.requests:
                del self.requests[identifier]

# Глобальный экземпляр rate limiter
rate_limiter = RateLimiter()
