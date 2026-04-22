import asyncio
import logging
import os
import sqlite3
from datetime import datetime

from aiogram import Bot, Dispatcher, Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

logging.basicConfig(level=logging.INFO)

API_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

bot = Bot(token=API_TOKEN)
dp = Dispatcher()
router = Router()

dp.include_router(router)

# ---------------- DATABASE ----------------
conn = sqlite3.connect("users.db")
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    created_at TEXT
)
""")
conn.commit()


# ---------------- KEYBOARDS ----------------
def main_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="⭐ Оплата", callback_data="pay"),
            InlineKeyboardButton(text="💰 Crypto", callback_data="crypto")
        ],
        [
            InlineKeyboardButton(text="🎁 Реферал", callback_data="ref"),
            InlineKeyboardButton(text="📅 Подписка", callback_data="sub")
        ],
        [
            InlineKeyboardButton(text="ℹ️ Информация", callback_data="info")
        ]
    ])


def info_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📄 Политика", callback_data="policy")],
        [InlineKeyboardButton(text="📑 Правила", callback_data="terms")],
        [InlineKeyboardButton(text="⬅ Назад", callback_data="back")]
    ])


# ---------------- START ----------------
@router.message(F.text == "/start")
async def start(message: Message):
    cursor.execute(
        "INSERT OR IGNORE INTO users (user_id, created_at) VALUES (?, ?)",
        (message.from_user.id, datetime.now().isoformat())
    )
    conn.commit()

    await message.answer(
        "🔒 Добро пожаловать в закрытый бот\n\n"
        "Выбери действие ниже:",
        reply_markup=main_kb()
    )


# ---------------- INFO ----------------
@router.callback_query(F.data == "info")
async def info(call: CallbackQuery):
    await call.message.edit_text(
        "ℹ️ Информация:",
        reply_markup=info_kb()
    )
    await call.answer()


@router.callback_query(F.data == "back")
async def back(call: CallbackQuery):
    await call.message.edit_text(
        "🔒 Главное меню:",
        reply_markup=main_kb()
    )
    await call.answer()


# ---------------- PLACEHOLDER MENUS ----------------
@router.callback_query(F.data == "pay")
async def pay(call: CallbackQuery):
    await call.message.answer("⭐ Оплата временно заглушка")
    await call.answer()


@router.callback_query(F.data == "crypto")
async def crypto(call: CallbackQuery):
    await call.message.answer("💰 Crypto меню (позже подключим Crypto Bot)")
    await call.answer()


@router.callback_query(F.data == "ref")
async def ref(call: CallbackQuery):
    bot_info = await bot.get_me()
    link = f"https://t.me/{bot_info.username}?start={call.from_user.id}"

    await call.message.answer(
        f"🎁 Твоя реферальная ссылка:\n{link}"
    )
    await call.answer()


@router.callback_query(F.data == "sub")
async def sub(call: CallbackQuery):
    await call.message.answer("📅 Подписка: заглушка")
    await call.answer()


# ---------------- SIMPLE DEBUG ----------------
@router.message()
async def echo(message: Message):
    await message.answer("бот работает ✅")


# ---------------- START BOT ----------------
async def main():
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
