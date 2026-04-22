import asyncio
import logging
import os
import sqlite3
from datetime import datetime, timedelta

import aiohttp
from aiogram import Bot, Dispatcher, F
from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    LabeledPrice,
    PreCheckoutQuery,
)

logging.basicConfig(level=logging.INFO)

API_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
GROUP_ID = int(os.getenv("TELEGRAM_GROUP_ID", "0"))
CRYPTO_TOKEN = os.getenv("CRYPTO_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0")) if os.getenv("ADMIN_ID") else None

if not API_TOKEN:
    raise RuntimeError("TELEGRAM_BOT_TOKEN не задан")


bot = Bot(API_TOKEN)
dp = Dispatcher()

conn = sqlite3.connect("users.db")
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    expire_date TEXT,
    ref_by INTEGER,
    refs_paid INTEGER DEFAULT 0
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

conn.commit()


PLANS = {
    "plan_1": (1, 550),
    "plan_7": (7, 770),
    "plan_30": (30, 1100),
}


# ---------------- PAYMENTS ----------------

async def create_invoice(amount: float, days: int):
    url = "https://pay.crypt.bot/api/createInvoice"
    headers = {"Crypto-Pay-API-Token": CRYPTO_TOKEN}

    async with aiohttp.ClientSession() as session:
        async with session.post(url, json={
            "asset": "USDT",
            "amount": amount,
            "description": f"{days}_days"
        }, headers=headers) as r:
            data = await r.json()

    return data["result"]


async def check_invoice(invoice_id: str):
    url = "https://pay.crypt.bot/api/getInvoices"
    headers = {"Crypto-Pay-API-Token": CRYPTO_TOKEN}

    async with aiohttp.ClientSession() as session:
        async with session.get(url, params={"invoice_ids": invoice_id}, headers=headers) as r:
            data = await r.json()

    return data["result"]["items"][0]["status"]


# ---------------- KEYBOARDS ----------------

def main_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⭐ Stars", callback_data="stars")],
        [InlineKeyboardButton(text="💰 Crypto", callback_data="crypto")],
        [InlineKeyboardButton(text="🎁 Ref", callback_data="ref")],
    ])


# ---------------- START ----------------

@dp.message(F.text.startswith("/start"))
async def start(message: Message):
    kb = main_kb()

    await message.answer(
        "Закрытый канал\nВыбери оплату:",
        reply_markup=kb
    )


# ---------------- MENU ----------------

@dp.callback_query(F.data == "stars")
async def stars(call: CallbackQuery):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="1 день", callback_data="plan_1")],
        [InlineKeyboardButton(text="7 дней", callback_data="plan_7")],
        [InlineKeyboardButton(text="30 дней", callback_data="plan_30")],
    ])

    await call.message.answer("Stars тарифы:", reply_markup=kb)
    await call.answer()


@dp.callback_query(F.data == "crypto")
async def crypto(call: CallbackQuery):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="1 день", callback_data="c_1")],
        [InlineKeyboardButton(text="7 дней", callback_data="c_7")],
        [InlineKeyboardButton(text="30 дней", callback_data="c_30")],
    ])

    await call.message.answer("Crypto тарифы:", reply_markup=kb)
    await call.answer()


# ---------------- STARS PAY ----------------

@dp.callback_query(F.data.in_({"plan_1", "plan_7", "plan_30"}))
async def stars_pay(call: CallbackQuery):
    days, price = PLANS[call.data]

    await bot.send_invoice(
        chat_id=call.message.chat.id,
        title=f"{days} days",
        description="Access",
        payload=call.data,
        provider_token="",
        currency="XTR",
        prices=[LabeledPrice(label="access", amount=price)],
    )

    await call.answer()


@dp.pre_checkout_query()
async def checkout(q: PreCheckoutQuery):
    await q.answer(ok=True)


@dp.message(F.successful_payment)
async def success(message: Message):
    payload = message.successful_payment.invoice_payload
    days = int(payload.split("_")[1])

    expire = datetime.now() + timedelta(days=days)

    cursor.execute(
        "INSERT OR REPLACE INTO users (user_id, expire_date) VALUES (?, ?)",
        (message.from_user.id, expire.isoformat())
    )
    conn.commit()

    invite = await bot.create_chat_invite_link(
        GROUP_ID,
        member_limit=1
    )

    await message.answer(f"Access until {expire.date()}\n{invite.invite_link}")


# ---------------- CRYPTO ----------------

@dp.callback_query(F.data.startswith("c_"))
async def crypto_pay(call: CallbackQuery):
    days = int(call.data.split("_")[1])
    amount = {1: 5, 7: 7, 30: 10}[days]

    invoice = await create_invoice(amount, days)

    cursor.execute(
        "INSERT INTO payments VALUES (?, ?, ?, ?)",
        (invoice["invoice_id"], call.from_user.id, days, "pending")
    )
    conn.commit()

    await call.message.answer(invoice["pay_url"])
    await call.answer()


# ---------------- POLLING ----------------

async def crypto_checker():
    while True:
        cursor.execute("SELECT invoice_id, user_id, days FROM payments WHERE status='pending'")
        rows = cursor.fetchall()

        for inv, uid, days in rows:
            try:
                status = await check_invoice(inv)
            except:
                continue

            if status == "paid":
                expire = datetime.now() + timedelta(days=days)

                cursor.execute(
                    "UPDATE users SET expire_date=? WHERE user_id=?",
                    (expire.isoformat(), uid)
                )

                cursor.execute(
                    "UPDATE payments SET status='paid' WHERE invoice_id=?",
                    (inv,)
                )

                conn.commit()

                invite = await bot.create_chat_invite_link(GROUP_ID, member_limit=1)

                await bot.send_message(uid, f"Paid OK\n{invite.invite_link}")

        await asyncio.sleep(20)


async def main():
    asyncio.create_task(crypto_checker())
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
