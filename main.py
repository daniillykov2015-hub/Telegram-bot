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

# Загрузка переменных окружения (Railway)
API_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
# Проверка наличия токена
if not API_TOKEN:
    logger.error("КРИТИЧЕСКАЯ ОШИБКА: TELEGRAM_BOT_TOKEN не найден!")

# Инициализация бота и диспетчера (в 3.x в Dispatcher не передаем bot)
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
        "Здесь ты можешь оформить подписку и получить доступ к эксклюзивному контенту.",
        reply_markup=get_start_kb()
    )

@dp.callback_query(F.data == "stars_menu")
async def stars_menu_handler(call: types.CallbackQuery):
    # Используем try/except, чтобы избежать ошибки "message is not modified"
    try:
        await call.message.edit_text(
            "💎 Выберите тариф для оплаты через Telegram Stars:",
            reply_markup=get_payment_kb()
        )
    except Exception as e:
        if "message is not modified" in str(e):
            await call.answer()
        else:
            logger.error(f"Ошибка при смене меню: {e}")
            await call.answer("Произошла ошибка, попробуйте снова.")

@dp.callback_query(F.data == "back_to_main")
async def back_handler(call: types.CallbackQuery):
    try:
        await call.message.edit_text(
            "🔒 Добро пожаловать в закрытый канал MistyBibi!\n\nВыбери действие:",
            reply_markup=get_start_kb()
        )
    except Exception as e:
        await call.answer()

@dp.message(Command("ping"))
async def ping_handler(message: types.Message):
    await message.answer("Бот жив и работает! ✅")

# --- Основная функция запуска ---

async def main():
    logger.info("Бот запускается...")
    try:
        # Удаляем вебхуки перед запуском polling
        await bot.delete_webhook(drop_pending_updates=True)
        await dp.start_polling(bot)
    except Exception as e:
        logger.error(f"Ошибка во время работы бота: {e}")
    finally:
        await bot.session.close()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Бот остановлен.")
