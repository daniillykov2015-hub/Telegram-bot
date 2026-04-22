import asyncio
import logging
import os
import sqlite3
from datetime import datetime, timedelta

import requests

from aiogram import Bot, Dispatcher, Router, F
from aiogram.filters import CommandStart
from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    LabeledPrice,
    PreCheckoutQuery,
    ChatMember,
    ChatInviteLink
)

# ================== CONFIG ==================
logging.basicConfig(level=logging.INFO)

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CRYPTO_TOKEN = os.getenv("CRYPTO_TOKEN")
CHANNEL_ID = int(os.getenv("TELEGRAM_GROUP_ID", "0"))
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))

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
CREATE TABLE IF NOT EXISTS payments (
    invoice_id TEXT,
    user_id INTEGER,
    days INTEGER,
    status TEXT
)
""")

conn.commit()

# ================== CACHE ==================
active_invoices = {}

# ================== PLANS ==================
PLANS = {
    "1": {"days": 1, "stars": 550, "crypto": 5},
    "7": {"days": 7, "stars": 770, "crypto": 7},
    "30": {"days": 30, "stars": 1100, "crypto": 10},
}

# ================== SAFE UI ==================
async def safe_update(call: CallbackQuery, text: str | None = None, markup=None):
    if text:
        await call.message.edit_text(text, reply_markup=markup)
    else:
        await call.message.edit_reply_markup(reply_markup=markup)
    await call.answer()

# ================== KEYBOARDS ==================
def menu(active=False):
    kb = [
        [
            InlineKeyboardButton(text="⭐ Stars", callback_data="stars"),
            InlineKeyboardButton(text="💰 Crypto", callback_data="crypto"),
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=kb)


def plans(prefix):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="1 день", callback_data=f"{prefix}:1")],
        [InlineKeyboardButton(text="7 дней", callback_data=f"{prefix}:7")],
        [InlineKeyboardButton(text="30 дней", callback_data=f"{prefix}:30")],
        [InlineKeyboardButton(text="⬅ Назад", callback_data="back")]
    ])


def pay(prefix, plan):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💳 Оплатить", callback_data=f"pay:{prefix}:{plan}")],
        [InlineKeyboardButton(text="⬅ Назад", callback_data="back")]
    ])

# ================== START ==================
@router.message(CommandStart())
async def start(message: Message):
    text = (
        "👋 Привет, я Ева и это мой закрытый канал\n\n"
        "❓ Что внутри?\n\n"
        "Закрытый контент по подписке\n\n"
        "💎 Без ограничений\n"
        "🔥 Обновления регулярно\n\n"
        "Выбери способ оплаты 👇"
    )

    await message.answer(text, reply_markup=menu())

# ================== NAV ==================
@router.callback_query(F.data == "back")
async def back(call: CallbackQuery):
    await safe_update(call, "Меню", menu())


@router.callback_query(F.data == "stars")
async def stars(call: CallbackQuery):
    await safe_update(call, "⭐ Тарифы", plans("stars"))


@router.callback_query(F.data == "crypto")
async def crypto(call: CallbackQuery):
    await safe_update(call, "💰 Тарифы", plans("crypto"))

# ================== PLANS ==================
@router.callback_query(F.data.startswith("stars:"))
async def stars_plan(call: CallbackQuery):
    plan = call.data.split(":")[1]
    await safe_update(
        call,
        f"{plan} дней — {PLANS[plan]['stars']}⭐",
        pay("stars", plan)
    )


@router.callback_query(F.data.startswith("crypto:"))
async def crypto_plan(call: CallbackQuery):
    plan = call.data.split(":")[1]
    await safe_update(
        call,
        f"{plan} дней — {PLANS[plan]['crypto']} USDT",
        pay("crypto", plan)
    )

# ================== STARS PAYMENT ==================
@router.callback_query(F.data.startswith("pay:stars:"))
async def pay_stars(call: CallbackQuery):
    await call.answer()  # ⚡ важно сразу убрать "loading"

    plan = call.data.split(":")[2]
    data = PLANS[plan]

    await bot.send_invoice(
        chat_id=call.message.chat.id,
        title="Access",
        description="Stars payment",
        payload=f"stars_{plan}",
        provider_token="",
        currency="XTR",
        prices=[LabeledPrice(label="Access", amount=data["stars"])]
    )

# ================== CRYPTO PAYMENT ==================
@router.callback_query(F.data.startswith("pay:crypto:"))
async def pay_crypto(call: CallbackQuery):
    await call.answer()  # ⚡ фикс зависания

    plan = call.data.split(":")[2]

    if call.from_user.id in active_invoices:
        await call.answer("⏳ Уже есть счёт", show_alert=True)
        return

    active_invoices[call.from_user.id] = plan
    data = PLANS[plan]

    r = requests.post(
        "https://pay.crypt.bot/api/createInvoice",
        headers={"Crypto-Pay-API-Token": CRYPTO_TOKEN},
        json={"asset": "USDT", "amount": data["crypto"]}
    ).json()

    invoice = r["result"]

    cursor.execute(
        "INSERT INTO payments VALUES (?, ?, ?, ?)",
        (invoice["invoice_id"], call.from_user.id, data["days"], "pending")
    )
    conn.commit()

    await call.message.answer(f"💰 Оплата:\n{invoice['pay_url']}")

# ================== RUN ==================
async def main():
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
