import asyncio
import logging
import os
import sqlite3
from datetime import datetime, timedelta

import requests
from aiogram import Bot, Dispatcher, Router, F
from aiogram.types import (
    Message, CallbackQuery,
    InlineKeyboardMarkup, InlineKeyboardButton,
    LabeledPrice, PreCheckoutQuery
)

logging.basicConfig(level=logging.INFO)

API_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
GROUP_ID = int(os.getenv("TELEGRAM_GROUP_ID", "0"))
CRYPTO_TOKEN = os.getenv("CRYPTO_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))

bot = Bot(API_TOKEN)
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
    refs_paid INTEGER DEFAULT 0,
    notified INTEGER DEFAULT 0
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

cursor.execute("""
CREATE TABLE IF NOT EXISTS logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    method TEXT,
    amount REAL,
    currency TEXT,
    created_at TEXT
)
""")

conn.commit()


# ---------------- PRICES ----------------
STARS = {1: 550, 7: 770, 30: 1100}
CRYPTO = {1: 5, 7: 7, 30: 10}


# ---------------- KEYBOARD ----------------
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
async def start(m: Message):
    args = m.text.split()

    ref = None
    if len(args) > 1 and args[1].isdigit():
        ref = int(args[1])

    cursor.execute(
        "INSERT OR IGNORE INTO users (user_id, ref_by) VALUES (?, ?)",
        (m.from_user.id, ref)
    )
    conn.commit()

    await m.answer("🔒 Добро пожаловать", reply_markup=main_kb())


# ---------------- INFO ----------------
@router.callback_query(F.data == "info")
async def info(c: CallbackQuery):
    await c.message.answer("ℹ️ Закрытый контент бот")
    await c.answer()


# ---------------- REF ----------------
@router.callback_query(F.data == "ref")
async def ref(c: CallbackQuery):
    bot_info = await bot.get_me()
    link = f"https://t.me/{bot_info.username}?start={c.from_user.id}"

    cursor.execute("SELECT refs_paid FROM users WHERE user_id=?", (c.from_user.id,))
    row = cursor.fetchone()

    await c.message.answer(
        f"🎁 ссылка:\n{link}\n\n"
        f"оплативших друзей: {row[0] if row else 0}"
    )
    await c.answer()


# ---------------- SUB ----------------
@router.callback_query(F.data == "sub")
async def sub(c: CallbackQuery):
    cursor.execute("SELECT expire_date FROM users WHERE user_id=?", (c.from_user.id,))
    row = cursor.fetchone()

    if not row or not row[0]:
        txt = "📅 нет подписки"
    else:
        txt = f"📅 до {row[0]}"

    await c.message.answer(txt)
    await c.answer()


# ---------------- STARS ----------------
@router.callback_query(F.data == "stars")
async def stars_menu(c: CallbackQuery):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="1 день", callback_data="s_1")],
        [InlineKeyboardButton(text="7 дней", callback_data="s_7")],
        [InlineKeyboardButton(text="30 дней", callback_data="s_30")]
    ])

    await c.message.answer("⭐ тарифы:", reply_markup=kb)


@router.callback_query(F.data.startswith("s_"))
async def stars_pay(c: CallbackQuery):
    days = int(c.data.split("_")[1])

    await bot.send_invoice(
        chat_id=c.from_user.id,
        title="Доступ",
        description="Закрытый контент",
        payload=f"stars_{days}",
        provider_token="",
        currency="XTR",
        prices=[LabeledPrice(label="access", amount=STARS[days])]
    )

    await c.answer()


# ---------------- CRYPTO ----------------
def create_invoice(amount, desc):
    r = requests.post(
        "https://pay.crypt.bot/api/createInvoice",
        headers={"Crypto-Pay-API-Token": CRYPTO_TOKEN},
        json={"asset": "USDT", "amount": amount, "description": desc}
    )
    return r.json()["result"]


@router.callback_query(F.data == "crypto")
async def crypto_menu(c: CallbackQuery):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="1", callback_data="c_1")],
        [InlineKeyboardButton(text="7", callback_data="c_7")],
        [InlineKeyboardButton(text="30", callback_data="c_30")]
    ])

    await c.message.answer("💰 crypto:", reply_markup=kb)


@router.callback_query(F.data.startswith("c_"))
async def crypto_pay(c: CallbackQuery):
    days = int(c.data.split("_")[1])
    inv = create_invoice(CRYPTO[days], f"{days} days")

    cursor.execute(
        "INSERT INTO payments VALUES (?, ?, ?, 'pending')",
        (inv["invoice_id"], c.from_user.id, days)
    )
    conn.commit()

    await c.message.answer(inv["pay_url"])


# ---------------- SUCCESS ----------------
@router.pre_checkout_query()
async def pre(q: PreCheckoutQuery):
    await bot.answer_pre_checkout_query(q.id, ok=True)


@router.message(F.successful_payment)
async def success(m: Message):
    days = int(m.successful_payment.invoice_payload.split("_")[1])

    expire = datetime.now() + timedelta(days=days)

    cursor.execute("""
        INSERT OR REPLACE INTO users (user_id, expire_date, notified)
        VALUES (?, ?, 0)
    """, (m.from_user.id, expire.isoformat()))

    conn.commit()

    await m.answer(f"✅ доступ до {expire.date()}")


# ---------------- ADMIN ----------------
@router.message(F.text.startswith("/give"))
async def give(m: Message):
    if m.from_user.id != ADMIN_ID:
        return

    _, uid, days = m.text.split()
    uid, days = int(uid), int(days)

    expire = datetime.now() + timedelta(days=days)

    cursor.execute("""
        INSERT OR REPLACE INTO users (user_id, expire_date)
        VALUES (?, ?)
    """, (uid, expire.isoformat()))

    conn.commit()

    await m.answer("выдано")


@router.message(F.text == "/stats")
async def stats(m: Message):
    if m.from_user.id != ADMIN_ID:
        return

    cursor.execute("SELECT COUNT(*) FROM users")
    users = cursor.fetchone()[0]

    await m.answer(f"users: {users}")


# ---------------- LOOP ----------------
async def check_expired():
    while True:
        now = datetime.now()

        cursor.execute("SELECT user_id, expire_date FROM users")
        for uid, exp in cursor.fetchall():
            if not exp:
                continue

            if datetime.fromisoformat(exp) < now:
                try:
                    await bot.ban_chat_member(GROUP_ID, uid)
                    await bot.unban_chat_member(GROUP_ID, uid)
                except:
                    pass

        await asyncio.sleep(300)


# ---------------- START ----------------
async def main():
    asyncio.create_task(check_expired())
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
