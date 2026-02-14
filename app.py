"""Refactored Flask application"""
import os
import logging
import time
import threading
from flask import Flask, request, jsonify, send_file, render_template, make_response
from flask_cors import CORS

from config import Config
from services.gpt_service import GPTService
from services.transcribe_service import TranscribeService
from services.file_service import FileService
from services.async_helper import run_async, _start_event_loop_thread
from save_results import save_to_files
from crud import save_intake, get_user_intakes, get_intake_by_id
from telegram_auth import send_message_to_telegram
from user_crud import get_user_by_session_id, get_or_create_user_by_session_id
from auth_codes import verify_auth_code
from utils.rate_limit import rate_limiter

# Инициализация приложения
app = Flask(__name__)
CORS(app)
Config.init_app(app)

# Блокировка для операций авторизации (убрана, т.к. вызывает проблемы с async)
# auth_lock = threading.Lock()  # Убрано - вызывает проблемы с event loop

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    handlers=[
        logging.FileHandler("app.log", encoding="utf-8"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


def get_client_identifier():
    """Получение идентификатора клиента для rate limiting"""
    return request.remote_addr or request.headers.get('X-Forwarded-For', 'unknown')


@app.route('/')
def index():
    """Главная (лендинг) страница"""
    response = make_response(render_template('home.html'))
    response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    return response


@app.route('/auth')
def auth_page():
    """Страница авторизации через Telegram"""
    response = make_response(render_template('auth.html'))
    response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    return response


@app.route('/app')
def app_recorder():
    """Интерфейс записи и анализа"""
    response = make_response(render_template('index.html'))
    response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    return response


@app.route('/api/upload', methods=['POST'])
def upload_audio():
    """Обработка загрузки аудио файла"""
    filepath = None
    try:
        # Rate limiting
        client_id = get_client_identifier()
        if not rate_limiter.is_allowed(client_id):
            return jsonify({'error': 'Превышен лимит запросов. Попробуйте позже.'}), 429
        
        logger.info("Получен запрос на загрузку аудио")
        
        # Проверка наличия файла
        if 'audio' not in request.files:
            logger.warning("Файл не найден в запросе")
            return jsonify({'error': 'Файл не найден'}), 400
        
        file = request.files['audio']
        
        # Валидация файла
        is_valid, error_msg = FileService.validate_file(file)
        if not is_valid:
            logger.warning(f"Валидация файла не пройдена: {error_msg}")
            return jsonify({'error': error_msg}), 400
        
        logger.info(f"Получен файл: {file.filename}, тип: {file.content_type}")
        
        # Сохранение файла
        filepath = FileService.save_uploaded_file(file)
        
        # Проверка размера файла
        is_valid_size, error_msg = FileService.validate_file_size(filepath)
        if not is_valid_size:
            FileService.cleanup_file(filepath)
            logger.warning(f"Файл слишком большой: {error_msg}")
            return jsonify({'error': error_msg}), 400
        
        # Транскрибация
        logger.info("Начало транскрибации...")
        preliminary_transcript = request.form.get('transcript', '').strip()
        
        try:
            transcribed_text = TranscribeService.transcribe_with_fallback(
                filepath, 
                preliminary_transcript
            )
            logger.info(f"Транскрибация завершена. Длина текста: {len(transcribed_text)} символов")
        except Exception as transcribe_error:
            FileService.cleanup_file(filepath)
            logger.error(f"Ошибка транскрибации: {transcribe_error}", exc_info=True)
            return jsonify({'error': f'Ошибка транскрибации: {str(transcribe_error)}'}), 500
        
        # Структурирование
        logger.info("Начало структурирования через GPT...")
        try:
            structured_text = GPTService.structure_text(transcribed_text)
            logger.info(f"Структурирование завершено. Длина: {len(structured_text)} символов")
        except Exception as struct_error:
            FileService.cleanup_file(filepath)
            logger.error(f"Ошибка структурирования: {struct_error}", exc_info=True)
            return jsonify({
                'error': f'Ошибка структурирования через GPT: {str(struct_error)}'
            }), 500
        
        # Сохранение в файлы
        txt_path, docx_path = save_to_files(structured_text)
        logger.info(f"Результаты сохранены: {txt_path}, {docx_path}")
        
        # Получение пользователя и сохранение в БД
        session_id = request.form.get('session_id', 'web_user')
        user_id, telegram_id = _get_user_info(session_id)
        
        logger.info(f"Сохранение в БД для user_id: {user_id}, telegram_id: {telegram_id}, session_id: {session_id}")
        logger.info(f"Длина структурированного текста: {len(structured_text)} символов")
        
        try:
            intake_id = run_async(save_intake(user_id, structured_text, txt_path, docx_path, telegram_id=telegram_id))
            logger.info(f"✅ Данные сохранены в БД успешно. Intake ID: {intake_id}, user_id: {user_id}, telegram_id: {telegram_id}")
        except Exception as db_error:
            logger.error(f"❌ Ошибка при сохранении в БД: {db_error}", exc_info=True)
            # Продолжаем выполнение даже если БД не сохранила
        
        # Отправка результата в Telegram (асинхронно, не блокируем ответ)
        sent_to_telegram = False
        if telegram_id:
            _send_to_telegram_async(telegram_id, structured_text, txt_path, docx_path)
            sent_to_telegram = True
            logger.info(f"📤 Очередь на отправку в Telegram для telegram_id={telegram_id}")
        
        # Удаление временного файла
        FileService.cleanup_file(filepath)
        
        return jsonify({
            'success': True,
            'transcribed_text': transcribed_text,
            'structured_text': structured_text,
            'txt_path': txt_path,
            'docx_path': docx_path,
            'sent_to_telegram': sent_to_telegram
        })
    
    except Exception as e:
        logger.exception("Ошибка при обработке аудио")
        FileService.cleanup_file(filepath)
        return jsonify({'error': f'Ошибка обработки: {str(e)}'}), 500


def _get_user_info(session_id: str):
    # Returns: (user_id: int, telegram_id: int | None)
    """Получение информации о пользователе по session_id. Создает пользователя, если его нет."""
    try:
        # Получаем или создаем пользователя
        user = run_async(get_or_create_user_by_session_id(session_id))
        if user:
            logger.info(f"Пользователь найден/создан: user_id={user.id}, session_id={session_id}")
            return user.id, user.telegram_id
        else:
            # Это не должно произойти, но на всякий случай
            logger.error(f"Не удалось создать пользователя для session_id: {session_id}")
            user_id = hash(session_id) % (10**10)
            return user_id, None
    except Exception as e:
        logger.error(f"Ошибка при получении/создании пользователя: {e}", exc_info=True)
        # В случае ошибки используем хеш как fallback
        user_id = hash(session_id) % (10**10)
        return user_id, None


def _send_to_telegram_async(telegram_id: int, structured_text: str, txt_path: str, docx_path: str):
    """Отправка результата в Telegram в отдельном потоке"""
    import threading
    
    def send_async():
        try:
            import asyncio
            new_loop = asyncio.new_event_loop()
            asyncio.set_event_loop(new_loop)
            try:
                message_text = f"📋 <b>Результат анализа приёма</b>\n\n{structured_text}"
                txt_full_path = os.path.join(os.getcwd(), txt_path) if not os.path.isabs(txt_path) else txt_path
                docx_full_path = os.path.join(os.getcwd(), docx_path) if not os.path.isabs(docx_path) else docx_path
                files = {'txt': txt_full_path, 'docx': docx_full_path}
                new_loop.run_until_complete(send_message_to_telegram(telegram_id, message_text, files))
                logger.info(f"Результат отправлен в Telegram для telegram_id: {telegram_id}")
            finally:
                try:
                    pending = [t for t in asyncio.all_tasks(new_loop) if not t.done()]
                    if pending:
                        for task in pending:
                            task.cancel()
                        if pending:
                            new_loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
                except Exception:
                    pass
                if not new_loop.is_closed():
                    new_loop.close()
        except Exception as tg_error:
            logger.warning(f"Не удалось отправить в Telegram: {tg_error}")
    
    # Запускаем в отдельном потоке с небольшой задержкой
    threading.Timer(0.3, send_async).start()


# Тестовые записи для режима демо
DEMO_HISTORY = [
    {'id': 1, 'created_at': '12.02.2026 14:30', 'preview': 'Жалобы: рвота 2 дня. Анамнез: кошка, 5 лет. Диагноз: гастрит. Назначения: диета, противорвотное.',
     'result_text': '1. Жалобы: рвота в течение 2 дней, снижение аппетита.\n2. Анамнез: кошка, 5 лет, порода британская. Вакцинирована.\n3. Предварительный диагноз: острый гастрит.\n4. Предварительные назначения: диетический корм, противорвотное 1×2 р/д 3 дня.'},
    {'id': 2, 'created_at': '11.02.2026 10:15', 'preview': 'Жалобы: хромота. Анамнез: собака, лабрадор. Диагноз: растяжение связок. Назначения: покой, НПВС.',
     'result_text': '1. Жалобы: хромота на переднюю лапу, началась после прогулки.\n2. Анамнез: собака, лабрадор, 3 года. Травм не было.\n3. Предварительный диагноз: растяжение связок запястья.\n4. Предварительные назначения: покой 5–7 дней, НПВС по весу.'},
    {'id': 3, 'created_at': '10.02.2026 16:45', 'preview': 'Жалобы: зуд, расчёсы. Анамнез: собака, 2 года. Диагноз: аллергический дерматит.',
     'result_text': '1. Жалобы: сильный зуд, расчёсы на боках и ушах.\n2. Анамнез: собака, 2 года. Симптомы 3 недели, сезонное обострение.\n3. Предварительный диагноз: аллергический дерматит.\n4. Предварительные назначения: антигистаминное, местная обработка.'},
    {'id': 4, 'created_at': '09.02.2026 09:20', 'preview': 'Жалобы: диарея. Анамнез: щенок, 4 мес. Диагноз: парвовирусный энтерит исключён.',
     'result_text': '1. Жалобы: диарея 1 день, активность сохранена.\n2. Анамнез: щенок 4 месяца, привит по возрасту. Смена корма 3 дня назад.\n3. Предварительный диагноз: алиментарная диарея.\n4. Предварительные назначения: голодная диета 12 ч, энтеросорбент, пробиотик.'},
]


@app.route('/api/history', methods=['GET'])
def get_history():
    """Получение истории анализов"""
    try:
        session_id = request.args.get('session_id', 'web_user')
        if session_id == 'demo':
            return jsonify({'success': True, 'history': DEMO_HISTORY})
        user_id, telegram_id = _get_user_info(session_id)
        
        logger.info(f"Запрос истории для user_id: {user_id}, telegram_id: {telegram_id}, session_id: {session_id}")
        
        # Добавляем небольшую задержку для избежания concurrent запросов
        import time
        time.sleep(0.1)
        
        try:
            intakes = run_async(get_user_intakes(user_id, telegram_id=telegram_id))
            logger.info(f"📋 Получено записей из БД: {len(intakes) if intakes else 0} для user_id={user_id}, telegram_id={telegram_id}")
            if intakes:
                logger.info(f"📋 Первая запись: id={intakes[0].id}, created_at={intakes[0].created_at}, user_id={intakes[0].user_id}")
        except Exception as db_error:
            logger.error(f"❌ Ошибка БД при получении истории: {db_error}", exc_info=True)
            # Возвращаем пустую историю вместо ошибки
            return jsonify({'success': True, 'history': []})
        
        history = []
        if intakes:
            for intake in intakes[-10:]:  # Последние 10 записей
                try:
                    # Безопасное форматирование даты
                    if hasattr(intake.created_at, 'strftime'):
                        created_at_str = intake.created_at.strftime('%d.%m.%Y %H:%M')
                    else:
                        created_at_str = str(intake.created_at)
                    
                    history.append({
                        'id': intake.id,
                        'created_at': created_at_str,
                        'result_text': intake.result_text or '',
                        'preview': (intake.result_text[:100] + '...') if intake.result_text and len(intake.result_text) > 100 else (intake.result_text or '')
                    })
                except Exception as item_error:
                    logger.warning(f"Ошибка обработки записи истории {intake.id}: {item_error}")
                    continue
        
        return jsonify({'success': True, 'history': history})
    
    except Exception as e:
        logger.exception("Ошибка при получении истории")
        # Возвращаем пустую историю вместо ошибки 500
        return jsonify({'success': True, 'history': []})


@app.route('/api/intake/<int:intake_id>', methods=['GET'])
def get_intake(intake_id):
    """Получение конкретного анализа"""
    try:
        if request.args.get('demo') == '1' and 1 <= intake_id <= 4:
            demo_item = next((h for h in DEMO_HISTORY if h['id'] == intake_id), None)
            if demo_item:
                return jsonify({
                    'success': True,
                    'intake': {
                        'id': demo_item['id'],
                        'created_at': demo_item['created_at'],
                        'result_text': demo_item['result_text'],
                        'txt_path': None,
                        'docx_path': None
                    }
                })
        logger.info(f"Запрос анализа с id: {intake_id}")
        intake = run_async(get_intake_by_id(intake_id))
        if not intake:
            return jsonify({'error': 'Запись не найдена'}), 404
        
        return jsonify({
            'success': True,
            'intake': {
                'id': intake.id,
                'created_at': intake.created_at.strftime('%d.%m.%Y %H:%M'),
                'result_text': intake.result_text,
                'txt_path': intake.txt_path,
                'docx_path': intake.docx_path
            }
        })
    
    except Exception as e:
        logger.exception("Ошибка при получении анализа")
        return jsonify({'error': f'Ошибка: {str(e)}'}), 500


@app.route('/api/download/<path:filename>', methods=['GET'])
def download_file(filename):
    """Скачивание файла"""
    try:
        filepath = os.path.join(os.getcwd(), filename)
        if os.path.exists(filepath):
            return send_file(filepath, as_attachment=True)
        else:
            return jsonify({'error': 'Файл не найден'}), 404
    except Exception as e:
        logger.exception("Ошибка при скачивании файла")
        return jsonify({'error': f'Ошибка: {str(e)}'}), 500


@app.route('/api/telegram/auth', methods=['POST'])
def telegram_auth():
    """Авторизация через Telegram (через код от бота)"""
    try:
        data = request.json
        if not data:
            return jsonify({'error': 'Данные не предоставлены'}), 400
        
        auth_code = data.get('code', '').strip().upper()
        session_id = data.get('session_id') or request.headers.get('X-Session-Id') or f"web_{int(time.time() * 1000)}"
        
        if not auth_code:
            return jsonify({'error': 'Код авторизации не предоставлен'}), 400
        
        logger.info(f"🔐 Попытка авторизации: code={auth_code[:4]}..., session_id={session_id}")
        
        # Проверка кода авторизации
        try:
            code_data = run_async(verify_auth_code(auth_code))
        except Exception as e:
            logger.error(f"❌ Ошибка при проверке кода: {e}", exc_info=True)
            return jsonify({'error': f'Ошибка проверки кода: {str(e)}'}), 500
        
        if not code_data:
            logger.warning(f"⚠️ Неверный или истекший код: {auth_code[:4]}...")
            return jsonify({'error': 'Неверный или истекший код авторизации'}), 401
        
        telegram_id = code_data['telegram_id']
        logger.info(f"✅ Код подтвержден для telegram_id={telegram_id}")
        
        # Связывание сессии с Telegram аккаунтом
        from user_crud import link_session_to_telegram
        try:
            success = run_async(link_session_to_telegram(session_id, telegram_id))
        except Exception as e:
            logger.error(f"❌ Ошибка при связывании сессии: {e}", exc_info=True)
            return jsonify({'error': f'Ошибка при связывании сессии: {str(e)}'}), 500
        
        if not success:
            logger.error(f"❌ Связывание сессии вернуло False")
            return jsonify({'error': 'Ошибка при связывании сессии'}), 500
        
        # Получение пользователя
        try:
            user = run_async(get_user_by_session_id(session_id))
        except Exception as e:
            logger.error(f"❌ Ошибка при получении пользователя: {e}", exc_info=True)
            return jsonify({'error': f'Ошибка получения пользователя: {str(e)}'}), 500
        
        if not user:
            logger.error(f"❌ Пользователь не найден после связывания: session_id={session_id}")
            return jsonify({'error': 'Пользователь не найден'}), 404
        
        logger.info(f"✅ Авторизация успешна: user_id={user.id}, telegram_id={user.telegram_id}")
        
        return jsonify({
            'success': True,
            'user': {
                'id': user.id,
                'telegram_id': user.telegram_id,
                'username': user.username or '',
                'first_name': user.first_name or '',
                'last_name': user.last_name or '',
                'photo_url': user.photo_url
            },
            'session_id': session_id
        })
    
    except Exception as e:
        logger.exception("❌ Критическая ошибка при авторизации через Telegram")
        return jsonify({'error': f'Ошибка авторизации: {str(e)}'}), 500


@app.route('/api/user/me', methods=['GET'])
def get_current_user():
    """Получение информации о текущем пользователе"""
    try:
        session_id = request.args.get('session_id')
        if not session_id:
            return jsonify({'success': False, 'user': None})
        
        logger.debug(f"🔍 Запрос пользователя: session_id={session_id}")
        
        try:
            user = run_async(get_user_by_session_id(session_id))
        except RuntimeError as e:
            if "Event loop is closed" in str(e) or "is closed" in str(e):
                logger.error(f"❌ Event loop закрыт при получении пользователя: {e}")
                # Повторяем попытку
                try:
                    user = run_async(get_user_by_session_id(session_id))
                except Exception as retry_e:
                    logger.error(f"❌ Ошибка при повторной попытке: {retry_e}", exc_info=True)
                    return jsonify({'success': False, 'user': None, 'error': 'Event loop error'})
            else:
                logger.error(f"❌ Ошибка при получении пользователя: {e}", exc_info=True)
                return jsonify({'success': False, 'user': None})
        except Exception as e:
            logger.error(f"❌ Ошибка при получении пользователя: {e}", exc_info=True)
            return jsonify({'success': False, 'user': None})
        
        if not user:
            logger.debug(f"👤 Пользователь не найден: session_id={session_id}")
            return jsonify({'success': False, 'user': None})
        
        logger.debug(f"✅ Пользователь найден: user_id={user.id}, telegram_id={user.telegram_id}")
        
        return jsonify({
            'success': True,
            'user': {
                'id': user.id,
                'telegram_id': user.telegram_id,
                'username': user.username,
                'first_name': user.first_name,
                'last_name': user.last_name,
                'photo_url': user.photo_url
            }
        })
    
    except Exception as e:
        logger.exception("❌ Критическая ошибка при получении пользователя")
        return jsonify({'success': False, 'user': None, 'error': str(e)})


@app.route('/profile')
def profile():
    """Страница личного кабинета"""
    response = make_response(render_template('profile.html'))
    response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    return response


if __name__ == '__main__':
    # Убеждаемся что event loop запущен перед стартом Flask
    try:
        _start_event_loop_thread()
        logger.info("🚀 Постоянный event loop запущен перед стартом Flask")
    except Exception as e:
        logger.error(f"❌ Ошибка при запуске event loop: {e}", exc_info=True)
    
    debug_mode = Config.DEBUG
    port = Config.PORT
    app.run(debug=debug_mode, host='0.0.0.0', port=port)
