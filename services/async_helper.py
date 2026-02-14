"""Вспомогательные функции для работы с async в синхронном контексте Flask"""
import asyncio
import concurrent.futures
import logging
import threading
try:
    from typing import Any, Coroutine
except ImportError:
    # Для старых версий Python
    Any = None
    Coroutine = None

logger = logging.getLogger(__name__)

# Глобальный постоянный event loop в отдельном потоке
_loop_thread = None
_loop = None
_loop_lock = threading.Lock()
_loop_ready = threading.Event()

def _start_event_loop_thread():
    """Запуск постоянного event loop в отдельном потоке"""
    global _loop_thread, _loop
    
    with _loop_lock:
        if _loop_thread is not None and _loop_thread.is_alive():
            if _loop is not None and not _loop.is_closed():
                return
        
        def _run_loop():
            """Запуск постоянного event loop"""
            global _loop
            try:
                _loop = asyncio.new_event_loop()
                asyncio.set_event_loop(_loop)
                _loop_ready.set()
                logger.info("✅ Постоянный event loop создан")
                
                # Запускаем loop навсегда
                _loop.run_forever()
            except Exception as e:
                logger.error(f"Ошибка в постоянном event loop: {e}", exc_info=True)
            finally:
                if _loop and not _loop.is_closed():
                    _loop.close()
                _loop = None
                _loop_ready.clear()
        
        _loop_ready.clear()
        _loop_thread = threading.Thread(target=_run_loop, daemon=True, name="AsyncEventLoop")
        _loop_thread.start()
        
        # Ждем пока loop создастся (максимум 5 секунд)
        if _loop_ready.wait(timeout=5):
            logger.info("✅ Постоянный event loop готов к работе")
        else:
            logger.error("❌ Таймаут при создании event loop")
            raise RuntimeError("Не удалось создать event loop за 5 секунд")

def _get_event_loop():
    """Получить постоянный event loop"""
    global _loop
    
    with _loop_lock:
        if _loop is None or _loop.is_closed():
            _start_event_loop_thread()
        
        # Проверяем еще раз после запуска
        if _loop is None or _loop.is_closed():
            raise RuntimeError("Event loop недоступен")
        
        return _loop

def run_async(coro):
    """
    Запуск async функции в синхронном контексте Flask
    
    Использует один постоянный event loop в отдельном потоке,
    который никогда не закрывается. Это решает проблему с SQLAlchemy async.
    """
    loop = _get_event_loop()
    
    try:
        # Используем run_coroutine_threadsafe для выполнения корутины в постоянном loop
        if asyncio.iscoroutine(coro):
            future = asyncio.run_coroutine_threadsafe(coro, loop)
        else:
            # Если это уже Future или другой объект
            future = asyncio.run_coroutine_threadsafe(asyncio.ensure_future(coro, loop=loop), loop)
        
        # Ждем результат с таймаутом
        try:
            result = future.result(timeout=60)
            return result
        except concurrent.futures.TimeoutError:
            logger.error("Таймаут при выполнении async функции")
            raise TimeoutError("Операция превысила таймаут 60 секунд")
        except Exception as e:
            logger.error(f"Ошибка при выполнении async функции: {e}", exc_info=True)
            raise
            
    except RuntimeError as e:
        if "Event loop is closed" in str(e) or "is closed" in str(e):
            logger.warning(f"Event loop был закрыт, перезапускаем: {e}")
            # Перезапускаем loop
            global _loop
            with _loop_lock:
                _loop = None
            loop = _get_event_loop()
            # Повторяем попытку
            future = asyncio.run_coroutine_threadsafe(coro, loop)
            return future.result(timeout=60)
        raise
    except Exception as e:
        logger.error(f"Критическая ошибка при выполнении async функции: {e}", exc_info=True)
        raise
