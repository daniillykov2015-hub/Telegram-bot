import asyncio
import logging
import os
import sqlite3
from datetime import datetime, timedelta

import aiohttp
from aiogram import Bot, Dispatcher, Router
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, LabeledPrice, PreCheckoutQuery

logging.basicConfig(level=logging.INFO)

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
GROUP_ID = int(os.getenv("TELEGRAM_GROUP_ID", "0"))
CRYPTO_TOKEN = os.getenv("CRYPTO_TOKEN")

if not TOKEN:
    raise RuntimeError("TELEGRAM_BOT_TOKEN не задан")


# ================= BOT =================

bot = Bot(TOKEN)
dp = Dispatcher()
router = Router()
dp.include_router(router)


# ================= DB =================

conn = sqlite3.connect("users.db")
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    expire_date TEXT
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


# ================= PAY =================

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


# ================= KEYBOARDS =================

def main_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⭐ Stars", callback_data="stars")],
        [InlineKeyboardButton(text="💰 Crypto", callback_data="crypto")],
    ])


def crypto_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="1 день", callback_data="c1")],
        [InlineKeyboardButton(text="7 дней", callback_data="c7")],
        [InlineKeyboardButton(text="30 дней", callback_data="c30")],
    ])


# ================= START =================

@router.message(Command("start"))
async def start(message: Message):
    await message.answer("Выбор оплаты:", reply_markup=main_kb())


# ================= MENU =================

@router.callback_query(lambda c: c.data == "crypto")
async def crypto(call: CallbackQuery):
    await call.message.answer("Crypto тарифы:", reply_markup=crypto_kb())
    await call.answer()


@router.callback_query(lambda c: c.data == "stars")
async def stars(call: CallbackQuery):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="1 день", callback_data="p1")],
        [InlineKeyboardButton(text="7 дней", callback_data="p7")],
        [InlineKeyboardButton(text="30 дней", callback_data="p30")],
    ])

    await call.message.answer("Stars тарифы:", reply_markup=kb)
    await call.answer()


# ================= CRYPTO =================

@router.callback_query(lambda c: c.data in ["c1", "c7", "c30"])
async def crypto_pay(call: CallbackQuery):
    days = {"c1": 1, "c7": 7, "c30": 30}[call.data]
    amount = {1: 5, 7: 7, 30: 10}[days]

    invoice = await create_invoice(amount, days)

    cursor.execute(
        "INSERT INTO payments VALUES (?, ?, ?, ?)",
        (invoice["invoice_id"], call.from_user.id, days, "pending")
    )
    conn.commit()

    await call.message.answer(invoice["pay_url"])
    await call.answer()


# ================= CHECKER =================

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
                    "INSERT OR REPLACE INTO users VALUES (?, ?)",
                    (uid, expire.isoformat())
                )

                cursor.execute(
                    "UPDATE payments SET status='paid' WHERE invoice_id=?",
                    (inv,)
                )

                conn.commit()

                invite = await bot.create_chat_invite_link(GROUP_ID, member_limit=1)

                await bot.send_message(uid, f"Оплачено ✅\n{invite.invite_link}")

        await asyncio.sleep(20)


# ================= STARS =================

@router.callback_query(lambda c: c.data in ["p1", "p7", "p30"])
async def stars_pay(call: CallbackQuery):
    days = {"p1": 1, "p7": 7, "p30": 30}[call.data]
    price = {1: 550, 7: 770, 30: 1100}[days]

    await bot.send_invoice(
        chat_id=call.message.chat.id,
        title="Access",
        description="Premium",
        payload=f"plan_{days}",
        provider_token="",
        currency="XTR",
        prices=[LabeledPrice(label="access", amount=price)],
    )

    await call.answer()


@router.pre_checkout_query()
async def checkout(q: PreCheckoutQuery):
    await q.answer(ok=True)


@router.message(lambda m: m.successful_payment)
async def success(message: Message):
    payload = message.successful_payment.invoice_payload
    days = int(payload.split("_")[1])

    expire = datetime.now() + timedelta(days=days)

    cursor.execute(
        "INSERT OR REPLACE INTO users VALUES (?, ?)",
        (message.from_user.id, expire.isoformat())
    )
    conn.commit()

    invite = await bot.create_chat_invite_link(GROUP_ID, member_limit=1)

    await message.answer(f"Доступ до {expire.date()}\n{invite.invite_link}")


# ================= MAIN =================

async def main():
    asyncio.create_task(crypto_checker())
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
