"""Refactored Telegram bot"""
import os
import asyncio
import logging
import time
from aiogram import Bot, Dispatcher, Router, types, F
from aiogram.types import FSInputFile, InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.dispatcher.middlewares.base import BaseMiddleware
from aiogram.dispatcher.event.bases import CancelHandler

from config import Config
from services.gpt_service import GPTService
from services.transcribe_service import TranscribeService
from save_results import save_to_files
from crud import save_intake, get_user_intakes, get_intake_by_id
from auth_codes import generate_auth_code
from user_crud import get_or_create_user_by_telegram

# Инициализация бота
bot = Bot(token=Config.API_TOKEN)
dp = Dispatcher()
router = Router()
dp.include_router(router)

user_files = {}

PROCESSING_FRAMES = [
    "🐾 Обработка…",
    "🐕 Анализ…",
    "🦴 Структурирую текст…",
    "🐈 Формирую результат…"
]
ANIMATION_DELAY = 0.14


# ------------------- Middleware -------------------
class LoggingMiddleware(BaseMiddleware):
    async def __call__(self, handler, event, data):
        start_time = time.time()
        try:
            response = await handler(event, data)
            elapsed = time.time() - start_time
            logging.info(
                f"User: {getattr(event.from_user, 'id', '-')}, "
                f"Type: {type(event).__name__}, "
                f"Time: {elapsed:.2f}s"
            )
            return response
        except Exception as e:
            logging.exception("Ошибка в обработчике!")
            if hasattr(event, "answer"):
                await event.answer("🚨 Произошла техническая ошибка, попробуйте ещё раз или обратитесь к администратору.")
            raise CancelHandler()

dp.message.middleware(LoggingMiddleware())
dp.callback_query.middleware(LoggingMiddleware())
# --------------------------------------------------


@router.message(F.text == "/start")
async def handle_start(message: types.Message):
    await message.answer(
        "<b>🐾 VeteraAI — ассистент ветеринарного приёма</b>\n\n"
        "1️⃣ Просто <b>отправьте голосовое</b> с записью приёма.\n"
        "2️⃣ Получите готовый текст по разделам:\n"
        " • Жалобы\n"
        " • Анамнез\n"
        " • Предварительный диагноз\n"
        " • Предварительные назначения\n"
        " • Рекомендации\n\n"
        "🤖 <b>AI-ассистент сам выбирает самое важное из вашего разговора</b> — вам не нужно вручную сортировать фразы!\n\n"
        "🆕 <b>Команды:</b>\n"
        "<b>/history</b> — покажет список всех ваших анализов\n"
        "<b>/auth</b> — получить код для авторизации на сайте\n\n"
        "📋 Можно скачать .txt / .docx сразу после анализа!\n\n"
        "🚀 <i>Экономьте время на заполнении карт — фокусируйтесь на пациентах!</i>",
        parse_mode="HTML"
    )


@router.message(F.text == "/auth")
async def handle_auth(message: types.Message):
    """Генерация кода авторизации для веб-сайта"""
    # Сохраняем данные пользователя при генерации кода
    user_data = {
        'id': message.from_user.id,
        'first_name': message.from_user.first_name or '',
        'last_name': message.from_user.last_name or '',
        'username': message.from_user.username or '',
        'photo_url': None
    }
    
    # Сохраняем пользователя в БД
    try:
        await get_or_create_user_by_telegram(user_data)
        await asyncio.sleep(0.1)  # Небольшая задержка для завершения транзакции
    except Exception as e:
        logging.warning(f"Не удалось сохранить пользователя: {e}")
    
    # Генерируем код
    code = await generate_auth_code(message.from_user.id, session_id=None)
    await asyncio.sleep(0.1)
    
    await message.answer(
        f"🔐 <b>Код авторизации для сайта</b>\n\n"
        f"Ваш код: <code>{code}</code>\n\n"
        f"Введите этот код на сайте для авторизации.\n"
        f"Код действителен 5 минут.",
        parse_mode="HTML"
    )


@router.message(F.voice)
async def handle_voice(message: types.Message):
    """Обработка голосового сообщения"""
    processing_msg = await message.answer(PROCESSING_FRAMES[0])

    async def animate_processing():
        idx = 0
        while True:
            await asyncio.sleep(ANIMATION_DELAY)
            try:
                await processing_msg.edit_text(PROCESSING_FRAMES[idx % len(PROCESSING_FRAMES)])
                idx += 1
            except Exception:
                break

    anim_task = asyncio.create_task(animate_processing())

    voice_path = None
    mp3_path = None
    try:
        # Проверка размера файла
        voice_file = await bot.get_file(message.voice.file_id)
        if voice_file.file_size > Config.MAX_FILE_SIZE:
            anim_task.cancel()
            await processing_msg.edit_text(
                f"Файл слишком большой! Пожалуйста, отправьте аудио до 25 МБ."
            )
            return

        # Скачивание файла
        voice_path = f"voice_{message.message_id}.ogg"
        await bot.download_file(voice_file.file_path, voice_path)

        # Конвертация в mp3 (если нужно)
        mp3_path = voice_path.replace(".ogg", ".mp3")
        if os.path.exists(voice_path):
            # Используем ffmpeg для конвертации
            import subprocess
            try:
                subprocess.run(
                    ["ffmpeg", "-i", voice_path, "-y", mp3_path],
                    check=True,
                    capture_output=True,
                    timeout=30
                )
            except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
                # Если ffmpeg недоступен, используем оригинальный файл
                mp3_path = voice_path
                logging.warning("ffmpeg недоступен, используем оригинальный файл")

        # Транскрибация
        transcribed_text = TranscribeService.transcribe(mp3_path if os.path.exists(mp3_path) else voice_path)

        # Структурирование через GPT
        structured_text = GPTService.structure_text(transcribed_text)

        # Сохранение результатов
        txt_path, docx_path = save_to_files(structured_text)
        user_files[message.from_user.id] = {"txt": txt_path, "docx": docx_path}

        # Сохранение в БД
        await save_intake(
            message.from_user.id,
            structured_text,
            txt_path,
            docx_path,
            telegram_id=message.from_user.id
        )

        anim_task.cancel()
        try:
            await processing_msg.edit_text("✅ <b>Готово! Вот структурированный текст:</b>", parse_mode="HTML")
        except:
            pass

        await message.answer(
            "📝 <b>Структурированный текст приёма:</b>\n\n" + structured_text,
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [
                    InlineKeyboardButton(text="📄 .txt", callback_data="download_txt"),
                    InlineKeyboardButton(text="🗂 .docx", callback_data="download_docx")
                ]
            ])
        )

    except Exception as e:
        anim_task.cancel()
        logging.exception("Ошибка при обработке голосового сообщения")
        await processing_msg.edit_text("❌ Произошла ошибка при обработке. Попробуйте ещё раз.")
        await message.answer(f"Ошибка: {str(e)}")

    finally:
        # Очистка временных файлов
        try:
            if voice_path and os.path.exists(voice_path):
                os.remove(voice_path)
            if mp3_path and os.path.exists(mp3_path) and mp3_path != voice_path:
                os.remove(mp3_path)
        except Exception:
            pass


@router.message(F.text == "/history")
async def handle_history(message: types.Message):
    """Показ истории анализов"""
    try:
        intakes = await get_user_intakes(message.from_user.id)
        if not intakes:
            await message.answer("У вас пока нет истории анализов.")
            return

        response = "<b>Ваша история анализов:</b>\n\n"
        keyboard = []
        for i, intake in enumerate(intakes[-10:], 1):
            text = f"{i}. {intake.created_at.strftime('%d.%m.%Y %H:%M')}\n<code>{intake.result_text[:80]}...</code>"
            keyboard.append(
                [InlineKeyboardButton(text=f"Показать полностью {i}", callback_data=f"show_{intake.id}")]
            )
            response += f"{text}\n\n"
        await message.answer(response, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard))
    except Exception as e:
        logging.exception("Ошибка при получении истории")
        await message.answer("❌ Произошла ошибка при получении истории.")


@router.callback_query(lambda c: c.data.startswith("show_"))
async def show_full_analysis(callback: types.CallbackQuery):
    """Показ полного анализа"""
    try:
        intake_id = int(callback.data.split("_")[1])
        intake = await get_intake_by_id(intake_id)
        if not intake:
            await callback.message.answer("Запись не найдена.")
            return
        await callback.message.answer(
            f"<b>Анализ от {intake.created_at.strftime('%d.%m.%Y %H:%M')}</b>\n\n"
            f"{intake.result_text}", parse_mode="HTML"
        )
    except Exception as e:
        logging.exception("Ошибка при показе анализа")
        await callback.message.answer("❌ Произошла ошибка.")


@router.callback_query(F.data == "download_txt")
async def handle_download_txt(callback: types.CallbackQuery):
    """Скачивание txt файла"""
    paths = user_files.get(callback.from_user.id)
    if paths and os.path.exists(paths["txt"]):
        await callback.message.answer_document(FSInputFile(paths["txt"]))
    else:
        await callback.message.answer("⛔️ Файл не найден. Пожалуйста, отправьте новое голосовое сообщение.")


@router.callback_query(F.data == "download_docx")
async def handle_download_docx(callback: types.CallbackQuery):
    """Скачивание docx файла"""
    paths = user_files.get(callback.from_user.id)
    if paths and os.path.exists(paths["docx"]):
        await callback.message.answer_document(FSInputFile(paths["docx"]))
    else:
        await callback.message.answer("⛔️ Файл не найден. Пожалуйста, отправьте новое голосовое сообщение.")


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(message)s",
        handlers=[
            logging.FileHandler("bot.log", encoding="utf-8"),
            logging.StreamHandler()
        ]
    )
    
    if not Config.API_TOKEN:
        logging.error("API_TOKEN не задан в .env! Бот не может запуститься.")
        logging.error("Добавьте API_TOKEN=ваш_токен_от_BotFather в файл .env")
        exit(1)
    
    async def main():
        await dp.start_polling(bot)
    
    asyncio.run(main())
