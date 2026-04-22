import asyncio
import logging
import os
import sqlite3
from datetime import datetime, timedelta

import requests
from aiogram import Bot, Dispatcher, Router, types, F
from aiogram.filters import CommandStart
from aiogram.types import (
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    LabeledPrice,
)

# ================== CONFIG ==================
logging.basicConfig(level=logging.INFO)

API_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
GROUP_ID = os.getenv("TELEGRAM_GROUP_ID")
CRYPTO_TOKEN = os.getenv("CRYPTO_TOKEN")

bot = Bot(token=API_TOKEN)
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


def back_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅ Назад", callback_data="back")]
    ])


def plan_menu(prefix: str):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton("1 день", callback_data=f"{prefix}_1")],
        [InlineKeyboardButton("7 дней", callback_data=f"{prefix}_7")],
        [InlineKeyboardButton("30 дней", callback_data=f"{prefix}_30")],
        [InlineKeyboardButton("⬅ Назад", callback_data="back")]
    ])


def pay_menu(prefix: str, plan: str):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton("💳 Оплатить", callback_data=f"pay_{prefix}_{plan}")],
        [InlineKeyboardButton("⬅ Назад", callback_data=f"{prefix}")]
    ])


# ================== START ==================
@router.message(CommandStart())
async def start(message: types.Message):
    await message.answer(
        "Добро пожаловать 👋\nВыбери оплату:",
        reply_markup=main_menu()
    )


# ================== MENU ==================
@router.callback_query(F.data == "back")
async def back(call: types.CallbackQuery):
    await call.message.edit_text("Главное меню:", reply_markup=main_menu())
    await call.answer()


@router.callback_query(F.data == "stars")
async def stars(call: types.CallbackQuery):
    await call.message.edit_text(
        "⭐ Выбери тариф Stars:",
        reply_markup=plan_menu("stars")
    )
    await call.answer()


@router.callback_query(F.data == "crypto")
async def crypto(call: types.CallbackQuery):
    await call.message.edit_text(
        "💰 Выбери тариф Crypto:",
        reply_markup=plan_menu("crypto")
    )
    await call.answer()


# ================== PLAN SCREENS ==================
@router.callback_query(F.data.startswith("stars_"))
async def stars_plan(call: types.CallbackQuery):
    plan = call.data.split("_")[1]

    await call.message.edit_text(
        f"⭐ Тариф {plan} дней\nЦена: {PLANS[plan]['stars']}⭐",
        reply_markup=pay_menu("stars", plan)
    )
    await call.answer()


@router.callback_query(F.data.startswith("crypto_"))
async def crypto_plan(call: types.CallbackQuery):
    plan = call.data.split("_")[1]

    await call.message.edit_text(
        f"💰 Тариф {plan} дней\nЦена: {PLANS[plan]['crypto']} USDT",
        reply_markup=pay_menu("crypto", plan)
    )
    await call.answer()


# ================== PAYMENT (STARS) ==================
@router.callback_query(F.data.startswith("pay_stars_"))
async def pay_stars(call: types.CallbackQuery):
    plan = call.data.split("_")[2]
    data = PLANS[plan]

    await bot.send_invoice(
        chat_id=call.message.chat.id,
        title=f"{data['days']} дней доступа",
        description="Оплата Stars",
        payload=f"stars_{plan}",
        provider_token="",
        currency="XTR",
        prices=[LabeledPrice(label="Access", amount=data["stars"])],
    )

    await call.message.answer(
        "🟡 Окно оплаты открыто.\nЕсли передумал — жми назад 👇",
        reply_markup=back_menu()
    )

    await call.answer()


# ================== PAYMENT (CRYPTO) ==================
def create_invoice(amount, payload):
    url = "https://pay.crypt.bot/api/createInvoice"
    headers = {"Crypto-Pay-API-Token": CRYPTO_TOKEN}
    data = {
        "asset": "USDT",
        "amount": amount,
        "description": payload
    }

    r = requests.post(url, headers=headers, json=data)
    return r.json()["result"]


@router.callback_query(F.data.startswith("pay_crypto_"))
async def pay_crypto(call: types.CallbackQuery):
    plan = call.data.split("_")[2]
    data = PLANS[plan]

    invoice = create_invoice(data["crypto"], f"{plan}_days")

    pay_url = invoice["pay_url"]
    invoice_id = invoice["invoice_id"]

    cursor.execute(
        "INSERT INTO payments VALUES (?, ?, ?, ?)",
        (invoice_id, call.from_user.id, data["days"], "pending")
    )
    conn.commit()

    await call.message.answer(
        f"💰 Оплати по ссылке:\n{pay_url}",
        reply_markup=back_menu()
    )

    await call.answer()


# ================== BACK BUTTON FROM PAY SCREEN ==================
@router.callback_query(F.data == "back")
async def back(call: types.CallbackQuery):
    await call.message.delete()
    await call.message.answer("Главное меню:", reply_markup=main_menu())
    await call.answer()


# ================== RUN ==================
async def main():
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
