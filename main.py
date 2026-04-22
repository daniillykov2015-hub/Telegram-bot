import asyncio
import logging
import os
import sqlite3
import requests

from aiogram import Bot, Dispatcher, Router, F
from aiogram.filters import CommandStart
from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    LabeledPrice
)

# ================== CONFIG ==================
logging.basicConfig(level=logging.INFO)

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
GROUP_ID = int(os.getenv("TELEGRAM_GROUP_ID", "0"))
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
    status TEXT
)
""")

conn.commit()

# ================== PRICES ==================
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


def back_to_main():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅ Назад", callback_data="back_main")]
    ])


def plans_menu(prefix: str):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="1 день", callback_data=f"{prefix}_1")],
        [InlineKeyboardButton(text="7 дней", callback_data=f"{prefix}_7")],
        [InlineKeyboardButton(text="30 дней", callback_data=f"{prefix}_30")],
        [InlineKeyboardButton(text="⬅ Назад", callback_data="back_main")]
    ])


def pay_menu(prefix: str, plan: str):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💳 Оплатить", callback_data=f"pay_{prefix}_{plan}")],
        [InlineKeyboardButton(text="⬅ Назад", callback_data=f"to_{prefix}")]
    ])


def back_to_plan(prefix: str):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅ Назад", callback_data=f"to_{prefix}")]
    ])

# ================== START ==================
@router.message(CommandStart())
async def start(message: Message):
    await message.answer(
        "👋 Выбери оплату:",
        reply_markup=main_menu()
    )

# ================== BACK MAIN ==================
@router.callback_query(F.data == "back_main")
async def back_main(call: CallbackQuery):
    await call.message.edit_text(
        "👋 Главное меню:",
        reply_markup=main_menu()
    )
    await call.answer()

# ================== RETURN TO MENU ==================
@router.callback_query(F.data == "to_stars")
async def to_stars(call: CallbackQuery):
    await call.message.edit_text(
        "⭐ Stars тарифы:",
        reply_markup=plans_menu("stars")
    )
    await call.answer()


@router.callback_query(F.data == "to_crypto")
async def to_crypto(call: CallbackQuery):
    await call.message.edit_text(
        "💰 Crypto тарифы:",
        reply_markup=plans_menu("crypto")
    )
    await call.answer()

# ================== MENUS ==================
@router.callback_query(F.data == "stars")
async def stars(call: CallbackQuery):
    await call.message.edit_text(
        "⭐ Stars тарифы:",
        reply_markup=plans_menu("stars")
    )
    await call.answer()


@router.callback_query(F.data == "crypto")
async def crypto(call: CallbackQuery):
    await call.message.edit_text(
        "💰 Crypto тарифы:",
        reply_markup=plans_menu("crypto")
    )
    await call.answer()

# ================== PLAN ==================
@router.callback_query(F.data.startswith("stars_"))
async def stars_plan(call: CallbackQuery):
    plan = call.data.split("_")[1]
    data = PLANS[plan]

    await call.message.edit_text(
        f"⭐ {data['days']} дней\nЦена: {data['stars']}⭐",
        reply_markup=pay_menu("stars", plan)
    )
    await call.answer()


@router.callback_query(F.data.startswith("crypto_"))
async def crypto_plan(call: CallbackQuery):
    plan = call.data.split("_")[1]
    data = PLANS[plan]

    await call.message.edit_text(
        f"💰 {data['days']} дней\nЦена: {data['crypto']} USDT",
        reply_markup=pay_menu("crypto", plan)
    )
    await call.answer()

# ================== STARS PAYMENT ==================
@router.callback_query(F.data.startswith("pay_stars_"))
async def pay_stars(call: CallbackQuery):
    plan = call.data.split("_")[2]
    data = PLANS[plan]

    await bot.send_invoice(
        chat_id=call.message.chat.id,
        title=f"{data['days']} дней доступа",
        description="Оплата Stars",
        payload=f"stars_{plan}",
        provider_token="",
        currency="XTR",
        prices=[LabeledPrice(label="Access", amount=data["stars"])]
    )

    await call.message.answer(
        "💳 Окно оплаты открыто",
        reply_markup=back_to_plan("stars")
    )

    await call.answer()

# ================== CRYPTO PAYMENT ==================
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
        "INSERT INTO payments VALUES (?, ?, ?, ?)",
        (invoice["invoice_id"], call.from_user.id, data["days"], "pending")
    )
    conn.commit()

    await call.message.answer(
        f"💰 Оплата:\n{invoice['pay_url']}",
        reply_markup=back_to_plan("crypto")
    )

    await call.answer()

# ================== RUN ==================
async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
