import asyncio
import logging
import os
import sqlite3
from datetime import datetime, timedelta

import requests
from aiogram import Bot, Dispatcher, Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.types import LabeledPrice, PreCheckoutQuery

logging.basicConfig(level=logging.INFO)

API_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
GROUP_ID = int(os.getenv("TELEGRAM_GROUP_ID", "0"))
CRYPTO_TOKEN = os.getenv("CRYPTO_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))

bot = Bot(token=API_TOKEN)
dp = Dispatcher()
router = Router()
dp.include_router(router)


# ---------------- DB ----------------
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


# ---------------- PRICING ----------------
STARS_PRICES = {
    1: 550,
    7: 770,
    30: 1100
}

CRYPTO_PRICES = {
    1: 5,
    7: 7,
    30: 10
}


# ---------------- KEYBOARDS ----------------
def main_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="⭐ Stars", callback_data="stars"),
            InlineKeyboardButton(text="💰 Crypto", callback_data="crypto")
        ],
        [
            InlineKeyboardButton(text="🎁 Реферал", callback_data="ref"),
            InlineKeyboardButton(text="📅 Подписка", callback_data="sub")
        ],
        [
            InlineKeyboardButton(text="ℹ️ Инфо", callback_data="info")
        ]
    ])


# ---------------- START ----------------
@router.message(F.text == "/start")
async def start(message: Message):
    cursor.execute(
        "INSERT OR IGNORE INTO users (user_id, expire_date) VALUES (?, NULL)",
        (message.from_user.id,)
    )
    conn.commit()

    await message.answer(
        "🔒 Добро пожаловать в закрытый бот\n\n"
        "Выбери действие:",
        reply_markup=main_kb()
    )


# ---------------- MENU ----------------
@router.callback_query(F.data == "info")
async def info(call: CallbackQuery):
    await call.message.answer("ℹ️ Информация о сервисе")
    await call.answer()


@router.callback_query(F.data == "ref")
async def ref(call: CallbackQuery):
    bot_info = await bot.get_me()
    link = f"https://t.me/{bot_info.username}?start={call.from_user.id}"

    await call.message.answer(f"🎁 Реферальная ссылка:\n{link}")
    await call.answer()


# ---------------- SUB ----------------
@router.callback_query(F.data == "sub")
async def sub(call: CallbackQuery):
    cursor.execute("SELECT expire_date FROM users WHERE user_id=?", (call.from_user.id,))
    row = cursor.fetchone()

    if not row or not row[0]:
        text = "📅 Подписка отсутствует"
    else:
        text = f"📅 Подписка до: {row[0]}"

    await call.message.answer(text)
    await call.answer()


# ---------------- STARS PAY ----------------
@router.callback_query(F.data == "stars")
async def stars_menu(call: CallbackQuery):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="1 день", callback_data="s_1")],
        [InlineKeyboardButton(text="7 дней", callback_data="s_7")],
        [InlineKeyboardButton(text="30 дней", callback_data="s_30")],
    ])

    await call.message.answer("⭐ Выбери тариф:", reply_markup=kb)
    await call.answer()


@router.callback_query(F.data.startswith("s_"))
async def pay_stars(call: CallbackQuery):
    days = int(call.data.split("_")[1])

    await bot.send_invoice(
        chat_id=call.from_user.id,
        title=f"{days} дней доступа",
        description="Закрытый контент",
        payload=f"stars_{days}",
        provider_token="",
        currency="XTR",
        prices=[LabeledPrice(label="Access", amount=STARS_PRICES[days])],
        start_parameter="pay"
    )

    await call.answer()


# ---------------- CRYPTO ----------------
def create_crypto_invoice(amount, desc):
    url = "https://pay.crypt.bot/api/createInvoice"
    headers = {"Crypto-Pay-API-Token": CRYPTO_TOKEN}

    r = requests.post(url, headers=headers, json={
        "asset": "USDT",
        "amount": amount,
        "description": desc
    })

    return r.json()["result"]


@router.callback_query(F.data == "crypto")
async def crypto_menu(call: CallbackQuery):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="1 день", callback_data="c_1")],
        [InlineKeyboardButton(text="7 дней", callback_data="c_7")],
        [InlineKeyboardButton(text="30 дней", callback_data="c_30")],
    ])

    await call.message.answer("💰 Crypto оплата:", reply_markup=kb)
    await call.answer()


@router.callback_query(F.data.startswith("c_"))
async def crypto_pay(call: CallbackQuery):
    days = int(call.data.split("_")[1])
    amount = CRYPTO_PRICES[days]

    invoice = create_crypto_invoice(amount, f"{days} days")

    cursor.execute(
        "INSERT INTO payments VALUES (?, ?, ?, ?)",
        (invoice["invoice_id"], call.from_user.id, days, "pending")
    )
    conn.commit()

    await call.message.answer(invoice["pay_url"])
    await call.answer()


# ---------------- PAYMENT SUCCESS ----------------
@router.pre_checkout_query()
async def pre_checkout(q: PreCheckoutQuery):
    await bot.answer_pre_checkout_query(q.id, ok=True)


@router.message(F.successful_payment)
async def success(message: Message):
    days = int(message.successful_payment.invoice_payload.split("_")[1])

    expire = datetime.now() + timedelta(days=days)

    cursor.execute("""
        INSERT OR REPLACE INTO users (user_id, expire_date)
        VALUES (?, ?)
    """, (message.from_user.id, expire.isoformat()))

    conn.commit()

    await message.answer(f"✅ Доступ до {expire.date()}")


# ---------------- RUN ----------------
async def main():
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
