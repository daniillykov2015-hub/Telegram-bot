import asyncio
import logging
import os
import requests
import sqlite3
from datetime import datetime, timedelta

from aiogram import Bot, Dispatcher, types
from aiogram.types import (
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    ContentType
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

API_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
GROUP_ID = os.getenv("TELEGRAM_GROUP_ID") or os.getenv("TELEGRAM_CHANNEL_ID")
CRYPTO_TOKEN = os.getenv("CRYPTO_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID")) if os.getenv("ADMIN_ID") else None

bot = Bot(token=API_TOKEN)
dp = Dispatcher()

# ---------------- DB ----------------
conn = sqlite3.connect("users.db", check_same_thread=False)
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

# ---------------- PLANS ----------------
PLANS = {
    "1": {"days": 1, "stars": 550, "crypto": 5},
    "7": {"days": 7, "stars": 770, "crypto": 7},
    "30": {"days": 30, "stars": 1100, "crypto": 10},
}

# ---------------- KEYBOARDS ----------------
def main_menu():
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(
        InlineKeyboardButton("⭐ Оплата", callback_data="stars_menu"),
        InlineKeyboardButton("💰 Crypto", callback_data="crypto_menu"),
    )
    kb.add(
        InlineKeyboardButton("👤 Мой аккаунт", callback_data="account"),
        InlineKeyboardButton("🎁 Рефералы", callback_data="ref_menu"),
    )
    kb.add(
        InlineKeyboardButton("ℹ️ Информация", callback_data="info_menu"),
    )
    return kb


def info_menu_kb():
    kb = InlineKeyboardMarkup(row_width=1)
    kb.add(
        InlineKeyboardButton("📄 Политика", callback_data="policy"),
        InlineKeyboardButton("📑 Условия", callback_data="terms"),
        InlineKeyboardButton("💬 Поддержка", url="https://t.me/mistybibi"),
        InlineKeyboardButton("⬅ Назад", callback_data="back_main"),
    )
    return kb


def back_kb():
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("⬅ Назад", callback_data="back_main"))
    return kb


# ---------------- START ----------------
@dp.message_handler(commands=["start"])
async def start(message: types.Message):
    await message.answer(
        "🔒 Добро пожаловать\n\n"
        "Это закрытый доступ.\n"
        "Выбери действие ниже:",
        reply_markup=main_menu()
    )


# ---------------- ACCOUNT ----------------
@dp.callback_query_handler(lambda c: c.data == "account")
async def account(call: types.CallbackQuery):
    cursor.execute("SELECT expire_date FROM users WHERE user_id=?", (call.from_user.id,))
    row = cursor.fetchone()

    text = "👤 АККАУНТ\n\n"

    if not row or not row[0]:
        text += "Подписка: отсутствует"
    else:
        text += f"Подписка до: {row[0]}"

    await call.message.answer(text, reply_markup=back_kb())
    await call.answer()


# ---------------- INFO ----------------
@dp.callback_query_handler(lambda c: c.data == "info_menu")
async def info(call: types.CallbackQuery):
    await call.message.answer("ℹ️ Информация", reply_markup=info_menu_kb())
    await call.answer()


@dp.callback_query_handler(lambda c: c.data == "policy")
async def policy(call: types.CallbackQuery):
    await call.message.answer("📄 Политика (упрощённая версия)...", reply_markup=back_kb())
    await call.answer()


@dp.callback_query_handler(lambda c: c.data == "terms")
async def terms(call: types.CallbackQuery):
    await call.message.answer("📑 Условия использования...", reply_markup=back_kb())
    await call.answer()


# ---------------- REF ----------------
@dp.callback_query_handler(lambda c: c.data == "ref_menu")
async def ref(call: types.CallbackQuery):
    bot_info = await bot.get_me()
    link = f"https://t.me/{bot_info.username}?start={call.from_user.id}"

    await call.message.answer(
        f"🎁 Рефералка\n\n{link}",
        reply_markup=back_kb()
    )
    await call.answer()


# ---------------- STARS / CRYPTO ----------------
@dp.callback_query_handler(lambda c: c.data == "stars_menu")
async def stars(call: types.CallbackQuery):
    kb = InlineKeyboardMarkup()
    kb.add(
        InlineKeyboardButton("1 день", callback_data="pay_1"),
        InlineKeyboardButton("7 дней", callback_data="pay_7"),
        InlineKeyboardButton("30 дней", callback_data="pay_30"),
    )
    kb.add(InlineKeyboardButton("⬅ Назад", callback_data="back_main"))

    await call.message.answer("⭐ Выбор тарифа", reply_markup=kb)
    await call.answer()


@dp.callback_query_handler(lambda c: c.data == "crypto_menu")
async def crypto(call: types.CallbackQuery):
    kb = InlineKeyboardMarkup()
    kb.add(
        InlineKeyboardButton("1 день", callback_data="crypto_1"),
        InlineKeyboardButton("7 дней", callback_data="crypto_7"),
        InlineKeyboardButton("30 дней", callback_data="crypto_30"),
    )
    kb.add(InlineKeyboardButton("⬅ Назад", callback_data="back_main"))

    await call.message.answer("💰 Crypto оплата", reply_markup=kb)
    await call.answer()


# ---------------- BACK ----------------
@dp.callback_query_handler(lambda c: c.data == "back_main")
async def back(call: types.CallbackQuery):
    await call.message.delete()
    await call.answer()


# ---------------- PAYMENTS (упрощённо оставил твои хуки) ----------------
@dp.pre_checkout_query_handler(lambda q: True)
async def checkout(q: types.PreCheckoutQuery):
    await bot.answer_pre_checkout_query(q.id, ok=True)


@dp.message_handler(content_types=ContentType.SUCCESSFUL_PAYMENT)
async def success(message: types.Message):
    await message.answer("Оплата получена ✅")


# ---------------- RUN ----------------
async def start_bot():
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(start_bot())
