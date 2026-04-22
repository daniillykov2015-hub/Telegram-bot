import asyncio
import logging
import os
import sqlite3
from datetime import datetime

# Исправленные импорты для aiogram 3.x
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Загрузка токена из Railway
API_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

# Инициализация (в 3.x бот передается только в polling)
bot = Bot(token=API_TOKEN)
dp = Dispatcher()

# --- Клавиатуры ---

def get_start_kb():
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="Оплата ⭐️", callback_data="stars_menu"))
    builder.row(InlineKeyboardButton(text="Crypto 💰", callback_data="crypto_menu"))
    builder.row(InlineKeyboardButton(text="Моя подписка 📅", callback_data="my_sub"))
    return builder.as_markup()

def get_payment_kb():
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="1 месяц — 500 ⭐", callback_data="buy_1m"))
    builder.row(InlineKeyboardButton(text="Назад", callback_data="back_to_main"))
    return builder.as_markup()

# --- Обработчики (Handlers) ---

@dp.message(Command("start"))
async def start_handler(message: types.Message):
    await message.answer(
        "🔒 Добро пожаловать в закрытый канал MistyBibi!\n\n"
        "Выберите действие:",
        reply_markup=get_start_kb()
    )

@dp.callback_query(F.data == "stars_menu")
async def stars_menu_handler(call: types.CallbackQuery):
    try:
        await call.message.edit_text(
            "💎 Тарифы для оплаты через Telegram Stars:",
            reply_markup=get_payment_kb()
        )
    except Exception as e:
        # Защита от ошибки "message is not modified"
        await call.answer()

@dp.callback_query(F.data == "back_to_main")
async def back_handler(call: types.CallbackQuery):
    try:
        await call.message.edit_text(
            "🔒 Добро пожаловать в закрытый канал MistyBibi!\n\nВыберите действие:",
            reply_markup=get_start_kb()
        )
    except Exception as e:
        await call.answer()

@dp.message(Command("ping"))
async def ping_handler(message: types.Message):
    await message.answer("Бот онлайн и работает! ✅")

# --- Основная функция запуска ---

async def main():
    logger.info("Удаление старых запросов и запуск бота...")
    try:
        # drop_pending_updates=True исправляет ошибку ConflictError
        await bot.delete_webhook(drop_pending_updates=True)
        await dp.start_polling(bot)
    except Exception as e:
        logger.error(f"Ошибка при работе: {e}")
    finally:
        await bot.session.close()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Бот остановлен.")
