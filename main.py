import asyncio
import logging
import os
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

# Настройка логирования для отслеживания работы в Railway
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Загрузка токена из переменных окружения Railway
API_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

if not API_TOKEN:
    logger.error("КРИТИЧЕСКАЯ ОШИБКА: TELEGRAM_BOT_TOKEN не найден в настройках!")

# Инициализация бота и диспетчера (версия 3.x)
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

# --- Обработчики сообщений и кнопок ---

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
    """Переход в меню оплаты звездами"""
    try:
        # Текст изменен, чтобы избежать ошибки 'message is not modified'
        await call.message.edit_text(
            "💎 Выберите тариф для оплаты через Telegram Stars:",
            reply_markup=get_payment_kb()
        )
    except Exception as e:
        await call.answer()
        logger.warning(f"Ошибка при смене меню: {e}")

@dp.callback_query(F.data == "back_to_main")
async def back_handler(call: types.CallbackQuery):
    """Возврат в главное меню"""
    try:
        await call.message.edit_text(
            "🔒 Главное меню MistyBibi.\n\nВыберите действие:",
            reply_markup=get_start_kb()
        )
    except Exception as e:
        await call.answer()

@dp.message(Command("ping"))
async def ping_handler(message: types.Message):
    """Проверка доступности бота"""
    await message.answer("Бот онлайн! ✅")

# --- Запуск ---

async def main():
    logger.info("Удаление старых запросов и запуск бота...")
    try:
        # drop_pending_updates=True критически важен для Railway, чтобы избежать ConflictError
        await bot.delete_webhook(drop_pending_updates=True)
        await dp.start_polling(bot)
    except Exception as e:
        logger.error(f"Ошибка при работе бота: {e}")
    finally:
        await bot.session.close()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Работа бота завершена.")
