import asyncio
import logging
import os
import sqlite3
from datetime import datetime
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, LabeledPrice
from aiogram.utils.keyboard import InlineKeyboardBuilder

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Загрузка переменных окружения
API_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
GROUP_ID = os.getenv("TELEGRAM_GROUP_ID") or os.getenv("TELEGRAM_CHANNEL_ID")

# Инициализация бота и диспетчера
bot = Bot(token=API_TOKEN)
dp = Dispatcher()

# --- Вспомогательная функция для клавиатур ---
def get_start_kb():
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="Оплата ⭐️", callback_data="stars_menu"))
    builder.row(InlineKeyboardButton(text="Crypto 💰", callback_data="crypto_menu"))
    builder.row(InlineKeyboardButton(text="Моя подписка 📅", callback_data="my_sub"))
    return builder.as_markup()

# --- Обработчики ---

@dp.message(Command("start"))
async def start_handler(message: types.Message):
    await message.answer(
        "🔒 Добро пожаловать в закрытый канал MistyBibi!\n\n"
        "Выбери действие:",
        reply_markup=get_start_kb()
    )

@dp.callback_query(F.data == "stars_menu")
async def stars_menu_handler(call: types.CallbackQuery):
    await call.message.edit_text("Выбери тариф (Telegram Stars):", reply_markup=get_start_kb())
    await call.answer()

# --- Запуск ---
async def main():
    if not API_TOKEN:
        logger.error("TELEGRAM_BOT_TOKEN не найден в переменных окружения!")
        return
    
    logger.info("Запуск бота...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as e:
        logger.error(f"Ошибка запуска: {e}")
