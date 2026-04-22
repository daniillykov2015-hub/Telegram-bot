import asyncio
import logging
import os
import sqlite3
from datetime import datetime, timedelta

from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, CallbackQuery, LabeledPrice
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ContentType

import aiohttp

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("bot")

# =======================
# ENV
# =======================
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CRYPTO_TOKEN = os.getenv("CRYPTO_TOKEN")
GROUP_ID = os.getenv("TELEGRAM_GROUP_ID")

if not TOKEN:
    raise RuntimeError("TELEGRAM_BOT_TOKEN не задан")

bot = Bot(TOKEN)
dp = Dispatcher()

# =======================
# DB
# =======================
conn = sqlite3.connect("users.db")
cur = conn.cursor()

cur.execute("""
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    expire TEXT
)
""")

cur.execute("""
CREATE TABLE IF NOT EXISTS payments (
    invoice_id TEXT,
    user_id INTEGER,
    days INTEGER,
    status TEXT
)
""")
conn.commit()

# =======================
# PLANS
# =======================
PLANS = {
    "1": {"days": 1, "price": 6.5},
    "7": {"days": 7, "price": 9},
    "30": {"days": 30, "price": 13},
}

# =======================
# CRYPTO API (FIXED)
# =======================
async def create_invoice(amount: float, days: int):
    if not CRYPTO_TOKEN:
        raise Exception("No CRYPTO_TOKEN")

    url = "https://pay.crypt.bot/api/createInvoice"
    headers = {"Crypto-Pay-API-Token": CRYPTO_TOKEN}

    payload = {
        "asset": "USDT",
        "amount": amount,
        "description": f"{days} days access"
    }

    async with aiohttp.ClientSession() as session:
        async with session.post(url, json=payload, headers=headers) as r:
            data = await r.json()

    # 🔥 ЗАЩИТА ОТ КРИВОГО ОТВЕТА
    if not isinstance(data, dict):
        raise Exception("Bad crypto response (not dict)")

    if not data.get("ok"):
        raise Exception(f"Crypto API error: {data}")

    result = data.get("result")
    if not result:
        raise Exception(f"No result in response: {data}")

    return result


# =======================
# START
# =======================
@dp.message(Command("start"))
async def start(m: Message):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Crypto 💰", callback_data="crypto")],
    ])

    await m.answer("Выбери оплату:", reply_markup=kb)


# =======================
# CRYPTO MENU
# =======================
@dp.callback_query(F.data == "crypto")
async def crypto_menu(c: CallbackQuery):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="1 день", callback_data="c_1")],
        [InlineKeyboardButton(text="7 дней", callback_data="c_7")],
        [InlineKeyboardButton(text="30 дней", callback_data="c_30")],
    ])

    await c.message.answer("Выбери тариф:", reply_markup=kb)
    await c.answer()


# =======================
# CREATE INVOICE
# =======================
@dp.callback_query(F.data.startswith("c_"))
async def crypto_pay(c: CallbackQuery):
    plan = c.data.split("_")[1]
    p = PLANS[plan]

    try:
        invoice = await create_invoice(p["price"], p["days"])
    except Exception as e:
        log.error(f"crypto error: {e}")
        await c.message.answer("❌ Ошибка CryptoBot. Попробуй позже.")
        await c.answer()
        return

    invoice_id = invoice.get("invoice_id")
    pay_url = invoice.get("pay_url")

    if not invoice_id or not pay_url:
        await c.message.answer("❌ Ошибка создания счёта")
        return

    cur.execute(
        "INSERT INTO payments VALUES (?, ?, ?, ?)",
        (invoice_id, c.from_user.id, p["days"], "pending")
    )
    conn.commit()

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Я оплатил ✅", callback_data=f"check_{invoice_id}")]
    ])

    await c.message.answer(f"Оплати:\n{pay_url}", reply_markup=kb)
    await c.answer()


# =======================
# CHECK PAYMENT (SAFE)
# =======================
async def check_invoice(invoice_id: str):
    url = "https://pay.crypt.bot/api/getInvoices"
    headers = {"Crypto-Pay-API-Token": CRYPTO_TOKEN}

    async with aiohttp.ClientSession() as session:
        async with session.get(url, params={"invoice_ids": invoice_id}, headers=headers) as r:
            data = await r.json()

    if not data.get("ok"):
        return None

    items = data.get("result", {}).get("items", [])
    if not items:
        return None

    return items[0].get("status")


@dp.callback_query(F.data.startswith("check_"))
async def check(c: CallbackQuery):
    invoice_id = c.data.split("_")[1]

    status = await check_invoice(invoice_id)

    if status != "paid":
        await c.message.answer("⏳ Пока не оплачено")
        await c.answer()
        return

    cur.execute("SELECT days, user_id FROM payments WHERE invoice_id=?", (invoice_id,))
    row = cur.fetchone()

    if not row:
        await c.message.answer("Не найден платёж")
        return

    days, user_id = row

    expire = datetime.now() + timedelta(days=days)

    cur.execute("INSERT OR REPLACE INTO users VALUES (?, ?)", (user_id, expire.isoformat()))
    cur.execute("UPDATE payments SET status='paid' WHERE invoice_id=?", (invoice_id,))
    conn.commit()

    await c.message.answer(f"✅ Доступ до {expire.date()}")
    await c.answer()


# =======================
# RUN
# =======================
async def main():
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
