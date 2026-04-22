import asyncio
import logging
import os
import sqlite3
from datetime import datetime

# Современные импорты для aiogram 3.x
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Получение токена из переменных окружения Railway
API_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

# Инициализация (в версии 3.x Dispatcher не принимает bot при создании)
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
    """Обработка команды /start"""
    await message.answer(
        "🔒 Добро пожаловать в закрытый канал MistyBibi!\n\n"
        "Выберите действие:",
        reply_markup=get_start_kb()
    )

@dp.callback_query(F.data == "stars_menu")
async def stars_menu_handler(call: types.CallbackQuery):
    """Переход в меню оплаты. Используем try, чтобы избежать ошибки 'message is not modified'"""
    try:
        await call.message.edit_text(
            "💎 Выберите тариф для оплаты через Telegram Stars:",
            reply_markup=get_payment_kb()
        )
    except Exception:
        await call.answer()

@dp.callback_query(F.data == "back_to_main")
async def back_handler(call: types.CallbackQuery):
    """Возврат в главное меню"""
    try:
        await call.message.edit_text(
            "🔒 Главное меню MistyBibi.\n\nВыберите действие:",
            reply_markup=get_start_kb()
        )
    except Exception:
        await call.answer()

@dp.message(Command("ping"))
async def ping_handler(message: types.Message):
    """Проверка доступности бота"""
    await message.answer("Бот онлайн! ✅")

# --- Запуск ---

async def main():
    logger.info("Удаление старых запросов и запуск бота...")
    try:
        # Эта строка критически важна для Railway, чтобы убить старые процессы (ConflictError)
        await bot.delete_webhook(drop_pending_updates=True)
        await dp.start_polling(bot)
    finally:
        await bot.session.close()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Бот остановлен.")
