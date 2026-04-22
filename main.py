import asyncio
import logging
import os
import sqlite3
from datetime import datetime, timedelta

import requests
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

# ---------------- CONFIG ----------------
API_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
GROUP_ID = int(os.getenv("TELEGRAM_GROUP_ID", "0"))
CRYPTO_TOKEN = os.getenv("CRYPTO_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))

logging.basicConfig(level=logging.INFO)

bot = Bot(token=API_TOKEN)
dp = Dispatcher()

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
    invoice_id TEXT PRIMARY KEY,
    user_id INTEGER,
    days INTEGER,
    status TEXT
)
""")

conn.commit()

# ---------------- PRICES ----------------
PLANS = {
    "1": {"days": 1, "price": 5},
    "7": {"days": 7, "price": 7},
    "30": {"days": 30, "price": 10},
}

# ---------------- KEYBOARDS ----------------
def main_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💳 Оплата", callback_data="pay")],
        [InlineKeyboardButton(text="💰 Crypto", callback_data="crypto")],
        [InlineKeyboardButton(text="🎁 Рефералка", callback_data="ref")],
        [InlineKeyboardButton(text="📅 Подписка", callback_data="sub")],
    ])


def pay_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="1 день", callback_data="p_1")],
        [InlineKeyboardButton(text="7 дней", callback_data="p_7")],
        [InlineKeyboardButton(text="30 дней", callback_data="p_30")],
        [InlineKeyboardButton(text="⬅ Назад", callback_data="back")]
    ])


# ---------------- UTIL ----------------
def get_expire(user_id: int):
    cursor.execute("SELECT expire_date FROM users WHERE user_id=?", (user_id,))
    row = cursor.fetchone()
    if row and row[0]:
        return datetime.fromisoformat(row[0])
    return None


def set_expire(user_id: int, days: int):
    expire = datetime.now() + timedelta(days=days)

    cursor.execute("""
    INSERT INTO users (user_id, expire_date)
    VALUES (?, ?)
    ON CONFLICT(user_id) DO UPDATE SET expire_date=excluded.expire_date
    """, (user_id, expire.isoformat()))

    conn.commit()
    return expire


# ---------------- START ----------------
@dp.message(Command("start"))
async def start(message: types.Message):
    args = message.get_args()

    if args.isdigit():
        ref = int(args)
        if ref != message.from_user.id:
            cursor.execute("SELECT user_id FROM users WHERE user_id=?", (message.from_user.id,))
            if not cursor.fetchone():
                cursor.execute(
                    "INSERT INTO users (user_id, ref_by) VALUES (?, ?)",
                    (message.from_user.id, ref)
                )
                conn.commit()

    await message.answer(
        "🔥 PRO BOT ACTIVE\n\nВыбери действие:",
        reply_markup=main_kb()
    )


# ---------------- MENU ----------------
@dp.callback_query()
async def menu(call: types.CallbackQuery):
    await call.answer()
    data = call.data

    if data == "back":
        await call.message.edit_text("Главное меню", reply_markup=main_kb())

    elif data == "pay":
        await call.message.edit_text("Выбери тариф:", reply_markup=pay_kb())

    elif data == "sub":
        exp = get_expire(call.from_user.id)

        text = "Нет подписки ❌"
        if exp and exp > datetime.now():
            text = f"Активна до: {exp.strftime('%d.%m.%Y %H:%M')}"

        await call.message.edit_text(text, reply_markup=main_kb())

    elif data == "ref":
        link = f"https://t.me/{(await bot.get_me()).username}?start={call.from_user.id}"
        await call.message.edit_text(f"Рефералка:\n{link}", reply_markup=main_kb())

    elif data == "crypto":
        await call.message.edit_text("Crypto активируется...", reply_markup=main_kb())

    # ---------------- PAYMENT FLOW ----------------
    elif data.startswith("p_"):
        days = int(data.split("_")[1])
        price = PLANS[str(days)]["price"]

        expire = set_expire(call.from_user.id, days)

        invite = await bot.create_chat_invite_link(
            chat_id=GROUP_ID,
            member_limit=1
        )

        await call.message.edit_text(
            f"✅ Оплата подтверждена\n\n"
            f"Доступ до: {expire.strftime('%d.%m.%Y %H:%M')}\n\n"
            f"{invite.invite_link}",
            reply_markup=main_kb()
        )


# ---------------- CRYPTOBOT ----------------
def create_invoice(amount: float, user_id: int):
    url = "https://pay.crypt.bot/api/createInvoice"
    headers = {"Crypto-Pay-API-Token": CRYPTO_TOKEN}

    data = {
        "asset": "USDT",
        "amount": amount,
        "description": f"user_{user_id}"
    }

    r = requests.post(url, headers=headers, json=data)
    return r.json()


# ---------------- CHECK CRYPTO PAYMENTS ----------------
async def check_crypto():
    while True:
        cursor.execute("SELECT invoice_id, user_id, days FROM payments WHERE status='pending'")
        rows = cursor.fetchall()

        for invoice_id, user_id, days in rows:
            try:
                r = requests.get(
                    "https://pay.crypt.bot/api/getInvoices",
                    headers={"Crypto-Pay-API-Token": CRYPTO_TOKEN},
                    params={"invoice_ids": invoice_id}
                ).json()

                items = r.get("result", {}).get("items", [])

                if items and items[0]["status"] == "paid":
                    expire = set_expire(user_id, days)

                    invite = await bot.create_chat_invite_link(
                        chat_id=GROUP_ID,
                        member_limit=1
                    )

                    await bot.send_message(
                        user_id,
                        f"✅ Оплата прошла\n"
                        f"Доступ до: {expire.strftime('%d.%m.%Y')}\n\n"
                        f"{invite.invite_link}"
                    )

                    cursor.execute(
                        "UPDATE payments SET status='paid' WHERE invoice_id=?",
                        (invoice_id,)
                    )
                    conn.commit()

            except Exception as e:
                logging.warning(e)

        await asyncio.sleep(20)


# ---------------- SUB CHECK ----------------
async def check_subs():
    while True:
        now = datetime.now()

        cursor.execute("SELECT user_id, expire_date FROM users")
        rows = cursor.fetchall()

        for uid, exp in rows:
            if not exp:
                continue

            try:
                if datetime.fromisoformat(exp) < now:
                    await bot.send_message(uid, "❌ Подписка закончилась")
            except:
                pass

        await asyncio.sleep(300)


# ---------------- START ----------------
async def main():
    asyncio.create_task(check_subs())
    asyncio.create_task(check_crypto())
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
