import asyncio
import logging
import os
import sqlite3
from datetime import datetime, timedelta

from aiogram import Bot, Dispatcher, Router, F
from aiogram.filters import CommandStart
from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)

# ================== CONFIG ==================
logging.basicConfig(level=logging.INFO)

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
router = Router()
dp.include_router(router)

# ================== DB ==================
conn = sqlite3.connect("users.db")
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    expire_date TEXT
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS referrals (
    user_id INTEGER,
    referred_id INTEGER UNIQUE
)
""")

conn.commit()

# ================== MAIN TEXT ==================
MAIN_TEXT = (
    "👋 Привет, я Ева и это мой закрытый канал\n\n"
    "❓ Что внутри?\n\n"
    "Закрытый контент по подписке\n"
    "💎 Без ограничений\n"
    "🔥 Обновления регулярно\n\n"
    "Выбери способ оплаты 👇"
)

# ================== KEYBOARDS ==================
def menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="⭐ Stars", callback_data="stars"),
            InlineKeyboardButton(text="💰 Crypto", callback_data="crypto"),
        ],
        [
            InlineKeyboardButton(text="👥 Реферальная система", callback_data="ref")
        ],
        [
            InlineKeyboardButton(text="ℹ️ Информация", callback_data="info")
        ]
    ])


def back_main():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅ Назад", callback_data="back")]
    ])


def back_info():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅ Назад", callback_data="info")]
    ])

# ================== START ==================
@router.message(CommandStart())
async def start(message: Message):
    await message.answer(MAIN_TEXT, reply_markup=menu())

# ================== BACK ==================
@router.callback_query(F.data == "back")
async def back(call: CallbackQuery):
    await call.message.edit_text(MAIN_TEXT, reply_markup=menu())
    await call.answer()

# ================== REF ==================
@router.callback_query(F.data == "ref")
async def ref(call: CallbackQuery):
    user_id = call.from_user.id
    link = f"https://t.me/{(await bot.get_me()).username}?start={user_id}"

    cursor.execute("SELECT COUNT(*) FROM referrals WHERE user_id=?", (user_id,))
    count = cursor.fetchone()[0]

    text = (
        "👥 РЕФЕРАЛЬНАЯ СИСТЕМА\n\n"
        "💡 Как получить +7 дней:\n\n"
        "1️⃣ У тебя должна быть подписка\n"
        "2️⃣ Пригласи друга по ссылке\n"
        "3️⃣ Он оформляет доступ\n"
        "4️⃣ Ты получаешь +7 дней\n\n"
        f"🔗 Твоя ссылка:\n{link}\n\n"
        f"👤 Приглашено: {count}"
    )

    await call.message.edit_text(text, reply_markup=back_main())
    await call.answer()

# ================== INFO MENU ==================
@router.callback_query(F.data == "info")
async def info(call: CallbackQuery):
    text = "ℹ️ ИНФОРМАЦИЯ\n\nВыбери раздел 👇"

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🛠 Поддержка", callback_data="support")],
        [InlineKeyboardButton(text="📄 Политика конфиденциальности", callback_data="privacy")],
        [InlineKeyboardButton(text="📜 Пользовательское соглашение", callback_data="terms")],
        [InlineKeyboardButton(text="⬅ Назад", callback_data="back")]
    ])

    await call.message.edit_text(text, reply_markup=kb)
    await call.answer()

# ================== SUPPORT ==================
@router.callback_query(F.data == "support")
async def support(call: CallbackQuery):
    text = (
        "🛠 ПОДДЕРЖКА\n\n"
        "👉 https://t.me/mistybibi"
    )

    await call.message.edit_text(text, reply_markup=back_info())
    await call.answer()

# ================== PRIVACY ==================
@router.callback_query(F.data == "privacy")
async def privacy(call: CallbackQuery):
    text = """Политика конфиденциальности
Platega • 1 апреля в 20:29

Данная Политика конфиденциальности регламентирует сбор идентификаторов аккаунта, технической информации и истории взаимодействий для обеспечения работы сервиса, связи с пользователем и аналитики. Передача данных третьим лицам допускается только по закону, для выполнения обязательств или с согласия пользователя.
Администрация хранит информацию необходимый срок, применяет разумные меры защиты, но не гарантирует абсолютной безопасности. Пользователь自行承担 риски передачи данных и принимает любые изменения в политике, продолжая использовать сервис.

1. Общие положения
2. Сбор информации
3. Использование информации
4. Передача информации
5. Хранение и защита
6. Отказ от ответственности
7. Изменения"""

    await call.message.edit_text(text, reply_markup=back_info())
    await call.answer()

# ================== TERMS ==================
@router.callback_query(F.data == "terms")
async def terms(call: CallbackQuery):
    text = """Пользовательское соглашение
Platega • 1 апреля в 20:30

1. Общие положения
2. Характер услуг
3. Отказ от гарантий
4. Законность использования
5. Интеллектуальная собственность
6. Ограничение доступа
7. Платежи и возвраты
8. Конфиденциальность
9. Изменения условий
10. Контакты"""

    await call.message.edit_text(text, reply_markup=back_info())
    await call.answer()

# ================== RUN ==================
async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
