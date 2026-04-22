import asyncio
import logging
import os
import sqlite3
import requests
from datetime import datetime

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
CRYPTO_TOKEN = os.getenv("CRYPTO_TOKEN")
GROUP_ID = int(os.getenv("TELEGRAM_GROUP_ID", "0"))

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
router = Router()
dp.include_router(router)

# ================== DB ==================
conn = sqlite3.connect("users.db")
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS orders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    plan TEXT,
    method TEXT,
    status TEXT,
    invoice_id TEXT,
    created_at TEXT
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


def plans_menu(prefix: str):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="1 день", callback_data=f"{prefix}_1")],
        [InlineKeyboardButton(text="7 дней", callback_data=f"{prefix}_7")],
        [InlineKeyboardButton(text="30 дней", callback_data=f"{prefix}_30")],
        [InlineKeyboardButton(text="⬅ Назад", callback_data="back")]
    ])


def pay_menu(method: str, plan: str):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💳 Оплатить", callback_data=f"pay_{method}_{plan}")],
        [InlineKeyboardButton(text="⬅ Назад", callback_data="back")]
    ])

# ================== ACCESS ==================
async def give_access(user_id: int, days: int):
    expire = datetime.utcnow()

    await bot.send_message(
        GROUP_ID,
        f"👤 User {user_id} получил доступ на {days} дней"
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
    await call.message.edit_text("⭐ Stars тарифы:", reply_markup=plans_menu("stars"))
    await call.answer()


@router.callback_query(F.data == "crypto")
async def crypto(call: CallbackQuery):
    await call.message.edit_text("💰 Crypto тарифы:", reply_markup=plans_menu("crypto"))
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

# ================== STARS (PROD) ==================
@router.callback_query(F.data.startswith("pay_stars_"))
async def pay_stars(call: CallbackQuery):
    plan = call.data.split("_")[2]
    data = PLANS[plan]

    cursor.execute("""
        INSERT INTO orders(user_id, plan, method, status, invoice_id, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (
        call.from_user.id,
        plan,
        "stars",
        "pending",
        "telegram",
        datetime.utcnow().isoformat()
    ))
    conn.commit()

    await bot.send_invoice(
        chat_id=call.message.chat.id,
        title=f"{data['days']} дней доступа",
        description="Stars payment",
        payload=f"stars_{plan}",
        provider_token="",
        currency="XTR",
        prices=[LabeledPrice(label="Access", amount=data["stars"])]
    )

    await call.message.answer("Ожидаем оплату ⭐")
    await call.answer()

# ================== PRECHECKOUT (CRITICAL) ==================
@router.pre_checkout_query()
async def pre_checkout(pre_checkout_q: PreCheckoutQuery):
    await bot.answer_pre_checkout_query(pre_checkout_q.id, ok=True)

# ================== SUCCESS STARS ==================
@router.message(F.successful_payment)
async def success_payment(message: Message):
    payload = message.successful_payment.invoice_payload
    plan = payload.split("_")[1]
    days = PLANS[plan]["days"]

    cursor.execute("""
        UPDATE orders SET status='paid'
        WHERE user_id=? AND method='stars'
        ORDER BY id DESC LIMIT 1
    """, (message.from_user.id,))
    conn.commit()

    await give_access(message.from_user.id, days)

    await message.answer("✅ Оплата прошла. Доступ выдан.")

# ================== CRYPTO ==================
def create_invoice(amount, payload):
    r = requests.post(
        "https://pay.crypt.bot/api/createInvoice",
        headers={"Crypto-Pay-API-Token": CRYPTO_TOKEN},
        json={
            "asset": "USDT",
            "amount": amount,
            "description": payload
        }
    )
    return r.json()["result"]


@router.callback_query(F.data.startswith("pay_crypto_"))
async def pay_crypto(call: CallbackQuery):
    plan = call.data.split("_")[2]
    data = PLANS[plan]

    invoice = create_invoice(data["crypto"], f"{plan}_days")

    cursor.execute("""
        INSERT INTO orders(user_id, plan, method, status, invoice_id, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (
        call.from_user.id,
        plan,
        "crypto",
        "pending",
        invoice["invoice_id"],
        datetime.utcnow().isoformat()
    ))
    conn.commit()

    await call.message.edit_text(
        f"💰 Оплата:\n{invoice['pay_url']}\n\nПосле оплаты доступ выдаётся автоматически."
    )

    await call.answer()

# ================== CRYPTO CHECK (simple poll) ==================
async def crypto_checker():
    while True:
        await asyncio.sleep(20)

        cursor.execute("SELECT id, user_id, plan, invoice_id FROM orders WHERE method='crypto' AND status='pending'")
        rows = cursor.fetchall()

        for row in rows:
            order_id, user_id, plan, invoice_id = row

            r = requests.get(
                f"https://pay.crypt.bot/api/getInvoices?invoice_ids={invoice_id}",
                headers={"Crypto-Pay-API-Token": CRYPTO_TOKEN}
            )

            result = r.json()["result"][0]

            if result["status"] == "paid":
                cursor.execute("UPDATE orders SET status='paid' WHERE id=?", (order_id,))
                conn.commit()

                await give_access(user_id, PLANS[plan]["days"])

                await bot.send_message(user_id, "✅ Crypto оплата прошла. Доступ выдан.")

# ================== RUN ==================
async def main():
    asyncio.create_task(crypto_checker())
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
