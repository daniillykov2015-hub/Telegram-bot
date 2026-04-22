import asyncio
import logging
import os
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

# Настройка логирования для Railway
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Токен из переменных окружения
API_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

if not API_TOKEN:
    logger.error("ОШИБКА: TELEGRAM_BOT_TOKEN не найден!")

# Инициализация бота и диспетчера (в 3.x бот не передается в Dispatcher)
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
    # Текст изменен, чтобы избежать совпадения при редактировании сообщения
    builder.row(InlineKeyboardButton(text="Купить за 500 ⭐", callback_data="buy_1m"))
    builder.row(InlineKeyboardButton(text="« Назад", callback_data="back_to_main"))
    return builder.as_markup()

# --- Обработчики ---

@dp.message(Command("start"))
async def start_handler(message: types.Message):
    await message.answer(
        "🔒 Добро пожаловать в закрытый канал MistyBibi!\n\nВыберите действие:",
        reply_markup=get_start_kb()
    )

@dp.callback_query(F.data == "stars_menu")
async def stars_menu_handler(call: types.CallbackQuery):
    try:
        # Текст обязательно должен отличаться от предыдущего (IMG_4631.jpg)
        await call.message.edit_text(
            "💎 Оплата через Telegram Stars.\nВыберите тариф:",
            reply_markup=get_payment_kb()
        )
    except Exception as e:
        logger.warning(f"Ошибка редактирования: {e}")
        await call.answer()

@dp.callback_query(F.data == "back_to_main")
async def back_handler(call: types.CallbackQuery):
    try:
        await call.message.edit_text(
            "🔒 Главное меню.\nВыберите действие:",
            reply_markup=get_start_kb()
        )
    except Exception:
        await call.answer()

# --- Запуск ---

async def main():
    logger.info("Запуск: удаление вебхуков и старых обновлений...")
    # Эта команда решает проблему TelegramConflictError (IMG_4632.jpg, IMG_4633.jpg)
    await bot.delete_webhook(drop_pending_updates=True)
    
    try:
        await dp.start_polling(bot)
    except Exception as e:
        logger.error(f"Критическая ошибка: {e}")
    finally:
        await bot.session.close()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Бот остановлен вручную.")
