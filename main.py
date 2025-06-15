import logging
import os
from aiogram import Bot, Dispatcher, types, executor
from transcribe_openai import transcribe_with_openai

API_TOKEN = os.getenv("API_TOKEN")

logging.basicConfig(level=logging.INFO)
bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot)

MAX_FILE_SIZE = 24 * 1024 * 1024  # 24 МБ — лимит OpenAI

@dp.message_handler(content_types=types.ContentType.VOICE)
async def handle_voice(message: types.Message):
    file_info = await bot.get_file(message.voice.file_id)
    if file_info.file_size > MAX_FILE_SIZE:
        await message.reply("Файл слишком большой! Пожалуйста, отправьте аудио до 5 минут (до 25 МБ).")
        return

    file_path = file_info.file_path
    destination = f"audio_{message.from_user.id}_{message.message_id}.ogg"
    await bot.download_file(file_path, destination)

    # (если надо — тут можешь вставить конвертацию ogg → mp3)

    try:
        text = transcribe_with_openai(destination)
        await message.reply(f"Расшифровка:\n{text}")
    except Exception as e:
        await message.reply(f"Ошибка при расшифровке: {e}")

if __name__ == "__main__":
    executor.start_polling(dp, skip_updates=True)
