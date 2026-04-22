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
GROUP_ID = int(os.getenv("TELEGRAM_GROUP_ID", "0"))
CRYPTO_TOKEN = os.getenv("CRYPTO_TOKEN")

if not BOT_TOKEN or not CRYPTO_TOKEN:
    raise RuntimeError("❌ Missing ENV variables")

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
active_invoices = {}  # user_id -> plan

# ================== PLANS ==================
PLANS = {
    "1": {"days": 1, "stars": 550, "crypto": 5},
    "7": {"days": 7, "stars": 770, "crypto": 7},
    "30": {"days": 30, "stars": 1100, "crypto": 10},
}

# ================== ACCESS ==================
async def grant_access(user_id: int, days: int):
    cursor.execute("SELECT expire_date FROM users WHERE user_id=?", (user_id,))
    row = cursor.fetchone()

    now = datetime.utcnow()

    if row and row[0]:
        current_expire = datetime.fromisoformat(row[0])
        if current_expire > now:
            new_expire = current_expire + timedelta(days=days)
        else:
            new_expire = now + timedelta(days=days)
    else:
        new_expire = now + timedelta(days=days)

    cursor.execute(
        "INSERT OR REPLACE INTO users VALUES (?, ?)",
        (user_id, new_expire.isoformat())
    )
    conn.commit()

    try:
        await bot.send_message(
            user_id,
            f"✅ Доступ активирован до:\n{new_expire.strftime('%Y-%m-%d %H:%M')}"
        )
    except:
        pass


# ================== KEYBOARDS ==================
def menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="⭐ Stars", callback_data="stars"),
            InlineKeyboardButton(text="💰 Crypto", callback_data="crypto"),
        ]
    ])


def plans(prefix: str):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="1 день", callback_data=f"{prefix}_1")],
        [InlineKeyboardButton(text="7 дней", callback_data=f"{prefix}_7")],
        [InlineKeyboardButton(text="30 дней", callback_data=f"{prefix}_30")],
        [InlineKeyboardButton(text="⬅ Назад", callback_data="back")]
    ])


def pay(prefix: str, plan: str):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💳 Оплатить", callback_data=f"pay_{prefix}_{plan}")],
        [InlineKeyboardButton(text="⬅ Назад", callback_data=prefix)]
    ])


# ================== START (WITH SUB CHECK) ==================
@router.message(CommandStart())
async def start(message: Message):
    cursor.execute("SELECT expire_date FROM users WHERE user_id=?", (message.from_user.id,))
    row = cursor.fetchone()

    if row and row[0]:
        expire = datetime.fromisoformat(row[0])
        if expire > datetime.utcnow():
            await message.answer(
                f"👋 У тебя активна подписка до:\n{expire.strftime('%Y-%m-%d %H:%M')}",
                reply_markup=menu()
            )
            return

    await message.answer("👋 Выбери оплату:", reply_markup=menu())


# ================== BACK ==================
@router.callback_query(F.data == "back")
async def back(call: CallbackQuery):
    await call.message.edit_text("Главное меню", reply_markup=menu())
    await call.answer()


# ================== MENUS ==================
@router.callback_query(F.data == "stars")
async def stars(call: CallbackQuery):
    await call.message.edit_text("⭐ Stars тарифы", reply_markup=plans("stars"))
    await call.answer()


@router.callback_query(F.data == "crypto")
async def crypto(call: CallbackQuery):
    await call.message.edit_text("💰 Crypto тарифы", reply_markup=plans("crypto"))
    await call.answer()


# ================== PLANS ==================
@router.callback_query(F.data.startswith("stars_"))
async def stars_plan(call: CallbackQuery):
    p = call.data.split("_")[1]
    await call.message.edit_text(
        f"⭐ {p} дней — {PLANS[p]['stars']}⭐",
        reply_markup=pay("stars", p)
    )
    await call.answer()


@router.callback_query(F.data.startswith("crypto_"))
async def crypto_plan(call: CallbackQuery):
    p = call.data.split("_")[1]
    await call.message.edit_text(
        f"💰 {p} дней — {PLANS[p]['crypto']} USDT",
        reply_markup=pay("crypto", p)
    )
    await call.answer()


# ================== STARS ==================
@router.callback_query(F.data.startswith("pay_stars_"))
async def pay_stars(call: CallbackQuery):
    plan = call.data.split("_")[2]
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

    await call.answer()


@router.pre_checkout_query()
async def pre_checkout(pre: PreCheckoutQuery):
    await pre.answer(ok=True)


@router.message(F.successful_payment)
async def stars_success(message: Message):
    payload = message.successful_payment.invoice_payload

    if payload.startswith("stars_"):
        plan = payload.split("_")[1]
        await grant_access(message.from_user.id, PLANS[plan]["days"])


# ================== CRYPTO (ANTI DUPLICATE) ==================
@router.callback_query(F.data.startswith("pay_crypto_"))
async def pay_crypto(call: CallbackQuery):
    plan = call.data.split("_")[2]

    # ❌ защита от дублей
    if call.from_user.id in active_invoices:
        await call.answer("⏳ Уже создан счёт", show_alert=True)
        return

    active_invoices[call.from_user.id] = plan
    data = PLANS[plan]

    url = "https://pay.crypt.bot/api/createInvoice"
    headers = {"Crypto-Pay-API-Token": CRYPTO_TOKEN}

    r = requests.post(url, headers=headers, json={
        "asset": "USDT",
        "amount": data["crypto"],
        "description": f"{plan} days access",
        "allow_comments": False
    })

    res = r.json()

    if not res.get("ok"):
        active_invoices.pop(call.from_user.id, None)
        await call.message.answer("❌ Ошибка платежа")
        return

    invoice = res["result"]

    cursor.execute(
        "INSERT INTO payments VALUES (?, ?, ?, ?)",
        (invoice["invoice_id"], call.from_user.id, data["days"], "pending")
    )
    conn.commit()

    await call.message.answer(f"💰 Оплата создана:\n{invoice['pay_url']}")
    await call.answer()


# ================== RUN ==================
async def main():
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
