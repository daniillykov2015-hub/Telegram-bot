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
    PreCheckoutQuery
)

# ================== CONFIG ==================
logging.basicConfig(level=logging.INFO)

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHANNEL_ID = int(os.getenv("TELEGRAM_GROUP_ID"))
CRYPTO_TOKEN = os.getenv("CRYPTO_TOKEN")

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
    method TEXT,
    status TEXT
)
""")

conn.commit()

# ================== PLANS ==================
PLANS = {
    "1": {"days": 1, "stars": 550, "crypto": 5},
    "7": {"days": 7, "stars": 770, "crypto": 7},
    "30": {"days": 30, "stars": 1100, "crypto": 10},
}

# ================== KEYBOARDS ==================
def main_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="⭐ Stars", callback_data="stars"),
            InlineKeyboardButton(text="💰 Crypto", callback_data="crypto"),
        ]
    ])

def back_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅ Назад", callback_data="back")]
    ])

def plan_menu(prefix):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton("1 день", callback_data=f"{prefix}_1")],
        [InlineKeyboardButton("7 дней", callback_data=f"{prefix}_7")],
        [InlineKeyboardButton("30 дней", callback_data=f"{prefix}_30")],
        [InlineKeyboardButton("⬅ Назад", callback_data="back")]
    ])

def pay_menu(prefix, plan):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton("💳 Оплатить", callback_data=f"pay_{prefix}_{plan}")],
        [InlineKeyboardButton("⬅ Назад", callback_data=prefix)]
    ])

# ================== ACCESS ==================
async def give_access(user_id: int):
    link = await bot.create_chat_invite_link(
        chat_id=CHANNEL_ID,
        member_limit=1,
        expire_date=datetime.now() + timedelta(minutes=15)
    )

    await bot.send_message(
        user_id,
        f"🔓 Доступ открыт:\n{link.invite_link}"
    )

# ================== START ==================
@router.message(CommandStart())
async def start(message: Message):
    await message.answer("Выбери оплату:", reply_markup=main_menu())

# ================== BACK ==================
@router.callback_query(F.data == "back")
async def back(call: CallbackQuery):
    await call.message.edit_text("Главное меню:", reply_markup=main_menu())
    await call.answer()

# ================== MENUS ==================
@router.callback_query(F.data == "stars")
async def stars(call: CallbackQuery):
    await call.message.edit_text("⭐ Stars тарифы:", reply_markup=plan_menu("stars"))
    await call.answer()

@router.callback_query(F.data == "crypto")
async def crypto(call: CallbackQuery):
    await call.message.edit_text("💰 Crypto тарифы:", reply_markup=plan_menu("crypto"))
    await call.answer()

# ================== PLANS ==================
@router.callback_query(F.data.startswith("stars_"))
async def stars_plan(call: CallbackQuery):
    plan = call.data.split("_")[1]
    data = PLANS[plan]

    await call.message.edit_text(
        f"⭐ {plan} дней\nЦена: {data['stars']}⭐",
        reply_markup=pay_menu("stars", plan)
    )
    await call.answer()

@router.callback_query(F.data.startswith("crypto_"))
async def crypto_plan(call: CallbackQuery):
    plan = call.data.split("_")[1]
    data = PLANS[plan]

    await call.message.edit_text(
        f"💰 {plan} дней\nЦена: {data['crypto']} USDT",
        reply_markup=pay_menu("crypto", plan)
    )
    await call.answer()

# ================== STARS PAY ==================
@router.pre_checkout_query()
async def pre_checkout(q: PreCheckoutQuery):
    await q.answer(ok=True)

@router.message(F.successful_payment)
async def stars_success(message: Message):
    payload = message.successful_payment.invoice_payload

    if payload.startswith("stars_"):
        await give_access(message.from_user.id)

# ================== CREATE INVOICE ==================
@router.callback_query(F.data.startswith("pay_stars_"))
async def pay_stars(call: CallbackQuery):
    plan = call.data.split("_")[2]
    data = PLANS[plan]

    await bot.send_invoice(
        chat_id=call.message.chat.id,
        title=f"{data['days']} дней",
        description="Stars access",
        payload=f"stars_{plan}",
        provider_token="",
        currency="XTR",
        prices=[LabeledPrice(label="Access", amount=data["stars"])]
    )

    await call.answer()

# ================== CRYPTO ==================
def create_invoice(amount, payload):
    url = "https://pay.crypt.bot/api/createInvoice"
    headers = {"Crypto-Pay-API-Token": CRYPTO_TOKEN}

    r = requests.post(url, headers=headers, json={
        "asset": "USDT",
        "amount": amount,
        "description": payload
    })

    return r.json()["result"]

@router.callback_query(F.data.startswith("pay_crypto_"))
async def pay_crypto(call: CallbackQuery):
    plan = call.data.split("_")[2]
    data = PLANS[plan]

    invoice = create_invoice(data["crypto"], f"{plan}_days")

    cursor.execute(
        "INSERT INTO payments VALUES (?, ?, ?, ?, ?)",
        (invoice["invoice_id"], call.from_user.id, data["days"], "crypto", "pending")
    )
    conn.commit()

    await call.message.answer(
        f"💰 Оплата:\n{invoice['pay_url']}"
    )

    # временно выдаём доступ (потом заменим на webhook)
    await give_access(call.from_user.id)

    await call.answer()

# ================== RUN ==================
async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
