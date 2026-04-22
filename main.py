import asyncio
import logging
import os
import requests
import sqlite3
from datetime import datetime, timedelta

from aiogram import Bot, Dispatcher, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.types import ContentType
from aiogram.utils import executor
from aiogram.filters import Command

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

API_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
GROUP_ID = os.getenv("TELEGRAM_GROUP_ID") or os.getenv("TELEGRAM_CHANNEL_ID")
CRYPTO_TOKEN = os.getenv("CRYPTO_TOKEN")
ADMIN_ID = os.getenv("ADMIN_ID")

try:
    ADMIN_ID = int(ADMIN_ID) if ADMIN_ID else None
except:
    ADMIN_ID = None


def is_admin(user_id: int) -> bool:
    return ADMIN_ID is not None and user_id == ADMIN_ID


# ⚠️ ВАЖНО: FIX — aiogram v2 требует bot в Dispatcher
bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot)


# ---------------- DATABASE ----------------
conn = sqlite3.connect("users.db")
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    expire_date TEXT,
    ref_by INTEGER,
    refs_paid INTEGER DEFAULT 0,
    notified INTEGER DEFAULT 0
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS payments (
    invoice_id TEXT,
    user_id INTEGER,
    days INTEGER,
    status TEXT
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS payments_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    method TEXT,
    days INTEGER,
    amount REAL,
    currency TEXT,
    created_at TEXT
)
""")

conn.commit()


# ---------------- START ----------------
@dp.message_handler(commands=["start"])
async def start(message: types.Message):
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(
        InlineKeyboardButton("Оплата ⭐️", callback_data="stars_menu"),
        InlineKeyboardButton("Crypto 💰", callback_data="crypto_menu"),
    )
    kb.add(
        InlineKeyboardButton("🎁 Реферал", callback_data="ref_menu"),
        InlineKeyboardButton("📅 Моя подписка", callback_data="my_sub"),
    )
    kb.add(
        InlineKeyboardButton("ℹ️ Информация", callback_data="info_menu"),
    )

    await message.answer(
        "🔒 Добро пожаловать!\n\n"
        "Выбери действие:",
        reply_markup=kb,
    )


# ---------------- INFO MENU ----------------
@dp.callback_query_handler(lambda c: c.data == "info_menu")
async def info_menu(call: types.CallbackQuery):
    kb = InlineKeyboardMarkup(row_width=1)
    kb.add(
        InlineKeyboardButton("Политика", callback_data="policy"),
        InlineKeyboardButton("Правила", callback_data="terms"),
        InlineKeyboardButton("Поддержка", url="https://t.me/your_support"),
        InlineKeyboardButton("⬅ Назад", callback_data="back_main"),
    )

    await call.message.answer("ℹ️ Информация:", reply_markup=kb)
    await call.answer()


# ---------------- BACK ----------------
@dp.callback_query_handler(lambda c: c.data == "back_main")
async def back_main(call: types.CallbackQuery):
    await call.message.delete()
    await call.answer()


# ---------------- SUBSCRIBE PAYLOAD ----------------
@dp.message_handler(content_types=ContentType.SUCCESSFUL_PAYMENT)
async def success(message: types.Message):
    await message.answer("Оплата получена ✅")


# ---------------- DEBUG ----------------
@dp.message_handler()
async def debug(message: types.Message):
    await message.answer("бот жив")


# ---------------- START BOT ----------------
if __name__ == "__main__":
    executor.start_polling(dp, skip_updates=True)
