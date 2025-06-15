import os
import asyncio
import logging
import time
from aiogram import Bot, Dispatcher, Router, types, F
from aiogram.types import FSInputFile, InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.dispatcher.middlewares.base import BaseMiddleware
from aiogram.dispatcher.event.bases import CancelHandler

from transcribe_openai import transcribe_audio
from save_results import save_to_files

from crud import save_intake, get_user_intakes, get_intake_by_id
from dotenv import load_dotenv
import openai

load_dotenv()
API_TOKEN = os.getenv("API_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

bot = Bot(token=API_TOKEN)
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
MAX_FILE_SIZE = 24 * 1024 * 1024  # 24 MB для OpenAI Whisper API

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

def structure_with_gpt(dialog_text):
    prompt = (
        "Ты — опытный ветеринарный врач в российской клинике. Пациент уже на приёме и осмотрен, диагноз формулируется по результатам осмотра и диалога.\n"
        "Тебе нужно:\n"
        "1. Извлечь только фактические 'Жалобы' и 'Анамнез' из разговора.\n"
        "2. Сформулировать предварительный диагноз ('Предварительный диагноз').\n"
        "3. В разделе 'Предварительные назначения' — отвечать для клиента, указывая конкретные препараты (торговые названия, если возможно), которые часто используются в России, а также зарубежные аналоги, если применяются. Не используй фразы «необходимо провести осмотр» или «точную дозировку определяет врач» — ты сам уже врач, дай рекомендации так, как будто ведёшь приём лично. Указывай примерную дозировку, если это безопасно. Если информации не хватает, напиши конкретно, какие данные ещё нужны.\n"
        "4. В 'Рекомендациях' — советы по уходу, транспорту, профилактике, наблюдению и дальнейшим действиям.\n"
        "Строго структурируй результат так:\n"
        "1. Жалобы: ...\n"
        "2. Анамнез: ...\n"
        "3. Предварительный диагноз: ...\n"
        "4. Предварительные назначения: ...\n"
        "5. Рекомендации: ...\n\n"
        "Текст диалога:\n" + dialog_text
    )
    client = openai.OpenAI(api_key=OPENAI_API_KEY)
    response = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[
            {"role": "system", "content": "Ты — опытный ветеринарный врач."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.2,
        max_tokens=1500,
    )
    return response.choices[0].message.content.strip()

@router.message(F.text == "/start")
async def handle_start(message: types.Message):
    await message.answer(
        "<b>🐾 VeteraAI — ассистент ветеринарного приёма</b>\n\n"
        "1️⃣ Просто <b>отправьте голосовое</b> с записью приёма.\n"
        "2️⃣ Получите готовый текст по разделам:\n"
        " • Жалобы\n"
        " • Анамнез\n"
        " • Предварительный диагноз\n"
        " • Предварительные назначения\n"
        " • Рекомендации\n\n"
        "🤖 <b>AI-ассистент сам выбирает самое важное из вашего разговора</b> — вам не нужно вручную сортировать фразы!\n\n"
        "🆕 <b>Новая команда:</b>\n"
        "<b>/history</b> — покажет список всех ваших анализов с кнопками «Показать полностью» для каждого случая.\n\n"
        "📋 Можно скачать .txt / .docx сразу после анализа!\n\n"
        "🚀 <i>Экономьте время на заполнении карт — фокусируйтесь на пациентах!</i>",
        parse_mode="HTML"
    )

@router.message(F.voice)
async def handle_voice(message: types.Message):
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
        voice_file = await bot.get_file(message.voice.file_id)
        if voice_file.file_size > MAX_FILE_SIZE:
            anim_task.cancel()
            await processing_msg.edit_text("Файл слишком большой! Пожалуйста, отправьте аудио до 5 минут (до 25 МБ).")
            return

        voice_path = f"voice_{message.message_id}.ogg"
        await bot.download_file(voice_file.file_path, voice_path)

        # Конвертация в mp3 (OpenAI принимает ogg/mp3/wav, но иногда лучше mp3)
        mp3_path = voice_path.replace(".ogg", ".mp3")
        os.system(f"ffmpeg -i {voice_path} {mp3_path}")

        # ---------- СТАДИЯ 1: транскрибация аудио ----------
        transcribed_text = transcribe_audio(mp3_path)

        # ---------- СТАДИЯ 2: структурирование через GPT ----------
        structured_text = structure_with_gpt(transcribed_text)

        # ---------- Сохранить результат в файлы и базу ----------
        txt_path, docx_path = save_to_files(structured_text)
        user_files[message.from_user.id] = {"txt": txt_path, "docx": docx_path}

        await save_intake(
            message.from_user.id,
            structured_text,
            txt_path,
            docx_path
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
        await processing_msg.edit_text("❌ Произошла ошибка при обработке. Попробуйте ещё раз.")
        await message.answer(f"Ошибка: {e}")

    finally:
        try:
            if voice_path and os.path.exists(voice_path):
                os.remove(voice_path)
            if mp3_path and os.path.exists(mp3_path):
                os.remove(mp3_path)
        except Exception:
            pass

@router.message(F.text == "/history")
async def handle_history(message: types.Message):
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

@router.callback_query(lambda c: c.data.startswith("show_"))
async def show_full_analysis(callback: types.CallbackQuery):
    intake_id = int(callback.data.split("_")[1])
    intake = await get_intake_by_id(intake_id)
    if not intake:
        await callback.message.answer("Запись не найдена.")
        return
    await callback.message.answer(
        f"<b>Анализ от {intake.created_at.strftime('%d.%m.%Y %H:%M')}</b>\n\n"
        f"{intake.result_text}", parse_mode="HTML"
    )

@router.callback_query(F.data == "download_txt")
async def handle_download_txt(callback: types.CallbackQuery):
    paths = user_files.get(callback.from_user.id)
    if paths and os.path.exists(paths["txt"]):
        await callback.message.answer_document(FSInputFile(paths["txt"]))
    else:
        await callback.message.answer("⛔️ Файл не найден. Пожалуйста, отправьте новое голосовое сообщение.")

@router.callback_query(F.data == "download_docx")
async def handle_download_docx(callback: types.CallbackQuery):
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
    async def main():
        await dp.start_polling(bot)
    asyncio.run(main())
