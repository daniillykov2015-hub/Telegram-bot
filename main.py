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
    LabeledPrice,
    ContentType
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# =====================
# ENV
# =====================
API_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
GROUP_ID = os.getenv("TELEGRAM_GROUP_ID")
CRYPTO_TOKEN = os.getenv("CRYPTO_TOKEN")
ADMIN_ID = os.getenv("ADMIN_ID")

if not API_TOKEN:
    raise RuntimeError("TELEGRAM_BOT_TOKEN не задан")

if not GROUP_ID:
    raise RuntimeError("TELEGRAM_GROUP_ID не задан")

GROUP_ID = int(GROUP_ID)

try:
    ADMIN_ID = int(ADMIN_ID) if ADMIN_ID else None
except:
    ADMIN_ID = None


# =====================
# BOT INIT (aiogram 2.x)
# =====================
bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot)


# =====================
# DB
# =====================
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


# =====================
# PLANS
# =====================
PLANS = {
    "plan_1": {"amount": 550, "title": "1 день", "days": 1},
    "plan_7": {"amount": 770, "title": "7 дней", "days": 7},
    "plan_30": {"amount": 1100, "title": "30 дней", "days": 30},
}


# =====================
# CRYPTO API
# =====================
class CryptoPayError(Exception):
    pass


def create_invoice(amount, payload):
    if not CRYPTO_TOKEN:
        raise CryptoPayError("CRYPTO_TOKEN не задан")

    r = requests.post(
        "https://pay.crypt.bot/api/createInvoice",
        headers={"Crypto-Pay-API-Token": CRYPTO_TOKEN},
        json={
            "asset": "USDT",
            "amount": amount,
            "description": payload,
        },
        timeout=15
    )

    data = r.json()

    if not data.get("ok"):
        raise CryptoPayError(data)

    return data["result"]


def check_invoice(invoice_id):
    r = requests.get(
        "https://pay.crypt.bot/api/getInvoices",
        headers={"Crypto-Pay-API-Token": CRYPTO_TOKEN},
        params={"invoice_ids": invoice_id},
        timeout=15
    )

    data = r.json()

    if not data.get("ok"):
        raise CryptoPayError(data)

    return data["result"]["items"][0]["status"]


# =====================
# KEYBOARDS
# =====================
def main_kb():
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(
        InlineKeyboardButton("⭐ Stars", callback_data="stars"),
        InlineKeyboardButton("💰 Crypto", callback_data="crypto"),
    )
    return kb


def plans_kb():
    kb = InlineKeyboardMarkup()
    kb.add(
        InlineKeyboardButton("1 день", callback_data="plan_1"),
        InlineKeyboardButton("7 дней", callback_data="plan_7"),
        InlineKeyboardButton("30 дней", callback_data="plan_30"),
    )
    return kb


# =====================
# START
# =====================
@dp.message_handler(commands=["start"])
async def start(m: types.Message):
    await m.answer("Бот работает ✅", reply_markup=main_kb())


# =====================
# MENUS
# =====================
@dp.callback_query_handler(lambda c: c.data == "stars")
async def stars(call: types.CallbackQuery):
    await call.message.answer("Тарифы:", reply_markup=plans_kb())
    await call.answer()


@dp.callback_query_handler(lambda c: c.data == "crypto")
async def crypto(call: types.CallbackQuery):
    await call.message.answer("Crypto тарифы:", reply_markup=plans_kb())
    await call.answer()


# =====================
# BUY
# =====================
@dp.callback_query_handler(lambda c: c.data.startswith("plan_"))
async def buy(call: types.CallbackQuery):
    plan = PLANS[call.data]

    invoice = create_invoice(plan["amount"], call.data)

    cursor.execute(
        "INSERT INTO payments VALUES (?, ?, ?, 'pending')",
        (invoice["invoice_id"], call.from_user.id, plan["days"])
    )
    conn.commit()

    kb = InlineKeyboardMarkup().add(
        InlineKeyboardButton("Проверить оплату", callback_data="check")
    )

    await call.message.answer(invoice["pay_url"], reply_markup=kb)
    await call.answer()


# =====================
# CHECK PAYMENT
# =====================
@dp.callback_query_handler(lambda c: c.data == "check")
async def check(call: types.CallbackQuery):
    cursor.execute(
        "SELECT invoice_id, days FROM payments WHERE user_id=? ORDER BY rowid DESC LIMIT 1",
        (call.from_user.id,)
    )
    row = cursor.fetchone()

    if not row:
        await call.message.answer("Счёт не найден")
        return

    invoice_id, days = row

    status = check_invoice(invoice_id)

    if status != "paid":
        await call.message.answer("Ещё не оплачено")
        return

    expire = datetime.now() + timedelta(days=days)

    cursor.execute("""
        INSERT OR REPLACE INTO users(user_id, expire_date, notified)
        VALUES (?, ?, 0)
    """, (call.from_user.id, expire.isoformat()))

    conn.commit()

    invite = await bot.create_chat_invite_link(
        chat_id=GROUP_ID,
        member_limit=1
    )

    await call.message.answer(
        f"Доступ до {expire.date()}\n{invite.invite_link}"
    )


# =====================
# SUBSCRIPTION
# =====================
@dp.callback_query_handler(lambda c: c.data == "sub")
async def sub(call: types.CallbackQuery):
    cursor.execute("SELECT expire_date FROM users WHERE user_id=?", (call.from_user.id,))
    row = cursor.fetchone()

    text = "Нет подписки"

    if row and row[0]:
        text = f"Действует до: {row[0]}"

    await call.message.answer(text)
    await call.answer()


# =====================
# SAFE START
# =====================
async def start_bot():
    try:
        await dp.start_polling()
    finally:
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(start_bot())
