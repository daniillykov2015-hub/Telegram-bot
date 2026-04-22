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


# ================== SAFE ENV SYSTEM ==================
def require_env(name: str, value: str | None, allow_int: bool = False):
    if not value:
        logging.error(f"❌ ENV ERROR: {name} не задан")
        return None

    if allow_int:
        try:
            return int(value)
        except ValueError:
            logging.error(f"❌ ENV ERROR: {name} должен быть числом: {value}")
            return None

    return value


BOT_TOKEN = require_env("TELEGRAM_BOT_TOKEN", os.getenv("TELEGRAM_BOT_TOKEN"))
GROUP_ID = require_env("TELEGRAM_GROUP_ID", os.getenv("TELEGRAM_GROUP_ID"), allow_int=True)
CRYPTO_TOKEN = require_env("CRYPTO_TOKEN", os.getenv("CRYPTO_TOKEN"))

if not BOT_TOKEN or not GROUP_ID or not CRYPTO_TOKEN:
    raise RuntimeError("❌ Бот не запущен: проверь TELEGRAM_BOT_TOKEN / TELEGRAM_GROUP_ID / CRYPTO_TOKEN")


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


# ================== ACCESS SYSTEM ==================
async def grant_access(user_id: int, days: int):
    expire = datetime.utcnow() + timedelta(days=days)

    cursor.execute(
        "INSERT OR REPLACE INTO users (user_id, expire_date) VALUES (?, ?)",
        (user_id, expire.isoformat())
    )
    conn.commit()

    try:
        await bot.send_message(user_id, f"✅ Доступ активирован на {days} дней!")
    except Exception as e:
        logging.error(f"ACCESS ERROR: {e}")


# ================== CRYPTO CHECK ==================
def check_crypto_invoice(invoice_id: str):
    url = "https://pay.crypt.bot/api/getInvoices"
    headers = {"Crypto-Pay-API-Token": CRYPTO_TOKEN}

    try:
        r = requests.post(url, headers=headers, json={"invoice_ids": invoice_id})
        data = r.json()
        return data["result"]["items"][0]["status"] == "paid"
    except Exception as e:
        logging.error(f"CRYPTO CHECK ERROR: {e}")
        return False


# ================== KEYBOARDS ==================
def main_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="⭐ Stars", callback_data="stars"),
            InlineKeyboardButton(text="💰 Crypto", callback_data="crypto"),
        ]
    ])


def plan_kb(prefix: str):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="1 день", callback_data=f"{prefix}_1")],
        [InlineKeyboardButton(text="7 дней", callback_data=f"{prefix}_7")],
        [InlineKeyboardButton(text="30 дней", callback_data=f"{prefix}_30")],
        [InlineKeyboardButton(text="⬅ Назад", callback_data="back")]
    ])


def pay_kb(prefix: str, plan: str):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💳 Оплатить", callback_data=f"pay_{prefix}_{plan}")],
        [InlineKeyboardButton(text="⬅ Назад", callback_data=prefix)]
    ])


# ================== START ==================
@router.message(CommandStart())
async def start(message: Message):
    await message.answer(
        "👋 Добро пожаловать!\nВыбери способ оплаты:",
        reply_markup=main_menu()
    )


# ================== BACK ==================
@router.callback_query(F.data == "back")
async def back(call: CallbackQuery):
    await call.message.edit_text(
        "Главное меню:",
        reply_markup=main_menu()
    )
    await call.answer()


# ================== MENUS ==================
@router.callback_query(F.data == "stars")
async def stars(call: CallbackQuery):
    await call.message.edit_text(
        "⭐ Выбери тариф Stars:",
        reply_markup=plan_kb("stars")
    )
    await call.answer()


@router.callback_query(F.data == "crypto")
async def crypto(call: CallbackQuery):
    await call.message.edit_text(
        "💰 Выбери тариф Crypto:",
        reply_markup=plan_kb("crypto")
    )
    await call.answer()


# ================== PLANS ==================
@router.callback_query(F.data.startswith("stars_"))
async def stars_plan(call: CallbackQuery):
    plan = call.data.split("_")[1]

    await call.message.edit_text(
        f"⭐ {plan} дней\nЦена: {PLANS[plan]['stars']}⭐",
        reply_markup=pay_kb("stars", plan)
    )
    await call.answer()


@router.callback_query(F.data.startswith("crypto_"))
async def crypto_plan(call: CallbackQuery):
    plan = call.data.split("_")[1]

    await call.message.edit_text(
        f"💰 {plan} дней\nЦена: {PLANS[plan]['crypto']} USDT",
        reply_markup=pay_kb("crypto", plan)
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
        description="Stars оплата",
        payload=f"stars_{plan}",
        provider_token="",
        currency="XTR",
        prices=[LabeledPrice(label="Access", amount=data["stars"])]
    )

    await call.answer()


# ================== STARS CONFIRM ==================
@router.pre_checkout_query()
async def pre_checkout(pre: PreCheckoutQuery):
    await pre.answer(ok=True)


@router.message(F.successful_payment)
async def success_payment(message: Message):
    payload = message.successful_payment.invoice_payload

    if payload.startswith("stars_"):
        plan = payload.split("_")[1]
        await grant_access(message.from_user.id, PLANS[plan]["days"])


# ================== CRYPTO PAYMENT ==================
@router.callback_query(F.data.startswith("pay_crypto_"))
async def pay_crypto(call: CallbackQuery):
    plan = call.data.split("_")[2]
    data = PLANS[plan]

    # временная заглушка инвойса (если у тебя уже есть create_invoice — подключишь)
    invoice_id = f"inv_{call.from_user.id}_{plan}"

    cursor.execute(
        "INSERT INTO payments VALUES (?, ?, ?, ?)",
        (invoice_id, call.from_user.id, data["days"], "pending")
    )
    conn.commit()

    await call.message.answer(
        "💰 Проверяем оплату...",
    )

    await asyncio.sleep(10)

    if check_crypto_invoice(invoice_id):
        await grant_access(call.from_user.id, data["days"])
    else:
        await call.message.answer("⏳ Оплата не найдена")

    await call.answer()


# ================== RUN ==================
async def main():
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
