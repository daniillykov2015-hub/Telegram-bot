import asyncio
import logging
import os
import sqlite3
from datetime import datetime, timedelta

import requests
from aiohttp import web

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
conn = sqlite3.connect("users.db", check_same_thread=False)
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
    status TEXT,
    created_at TEXT
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

def back():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅ Назад", callback_data="back")]
    ])

def plan(prefix):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton("1 день", callback_data=f"{prefix}_1")],
        [InlineKeyboardButton("7 дней", callback_data=f"{prefix}_7")],
        [InlineKeyboardButton("30 дней", callback_data=f"{prefix}_30")],
        [InlineKeyboardButton("⬅ Назад", callback_data="back")]
    ])

def pay(prefix, p):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton("💳 Оплатить", callback_data=f"pay_{prefix}_{p}")],
        [InlineKeyboardButton("⬅ Назад", callback_data=prefix)]
    ])

# ================== SUB LOGIC ==================
def add_days(user_id, days):
    cursor.execute("SELECT expire_date FROM users WHERE user_id=?", (user_id,))
    row = cursor.fetchone()

    now = datetime.now()

    if row and row[0]:
        current = datetime.fromisoformat(row[0])
        if current > now:
            now = current

    new_date = now + timedelta(days=days)

    cursor.execute("""
    INSERT INTO users (user_id, expire_date)
    VALUES (?, ?)
    ON CONFLICT(user_id) DO UPDATE SET expire_date=excluded.expire_date
    """, (user_id, new_date.isoformat()))

    conn.commit()

def is_active(user_id):
    cursor.execute("SELECT expire_date FROM users WHERE user_id=?", (user_id,))
    row = cursor.fetchone()

    if not row or not row[0]:
        return False

    return datetime.fromisoformat(row[0]) > datetime.now()

# ================== ACCESS ==================
async def give_access(user_id):
    try:
        link = await bot.create_chat_invite_link(
            chat_id=CHANNEL_ID,
            member_limit=1,
            expire_date=datetime.now() + timedelta(minutes=15)
        )

        await bot.send_message(user_id, f"🔓 Доступ:\n{link.invite_link}")
    except:
        pass

# ================== AUTO KICK ==================
async def kick(user_id):
    if not is_active(user_id):
        try:
            await bot.ban_chat_member(CHANNEL_ID, user_id)
            await bot.unban_chat_member(CHANNEL_ID, user_id)
        except:
            pass

async def checker():
    while True:
        cursor.execute("SELECT user_id FROM users")
        users = cursor.fetchall()

        for (uid,) in users:
            await kick(uid)

        await asyncio.sleep(60)

# ================== START ==================
@router.message(CommandStart())
async def start(m: Message):
    await m.answer("Выбери оплату:", reply_markup=main_menu())

# ================== BACK ==================
@router.callback_query(F.data == "back")
async def back_h(c: CallbackQuery):
    await c.message.edit_text("Меню:", reply_markup=main_menu())
    await c.answer()

# ================== MENUS ==================
@router.callback_query(F.data == "stars")
async def stars(c: CallbackQuery):
    await c.message.edit_text("⭐ тарифы:", reply_markup=plan("stars"))
    await c.answer()

@router.callback_query(F.data == "crypto")
async def crypto(c: CallbackQuery):
    await c.message.edit_text("💰 тарифы:", reply_markup=plan("crypto"))
    await c.answer()

# ================== PLANS ==================
@router.callback_query(F.data.startswith("stars_"))
async def stars_p(c: CallbackQuery):
    p = c.data.split("_")[1]
    d = PLANS[p]

    await c.message.edit_text(
        f"⭐ {p} дней\n{d['stars']}⭐",
        reply_markup=pay("stars", p)
    )
    await c.answer()

@router.callback_query(F.data.startswith("crypto_"))
async def crypto_p(c: CallbackQuery):
    p = c.data.split("_")[1]
    d = PLANS[p]

    await c.message.edit_text(
        f"💰 {p} дней\n{d['crypto']} USDT",
        reply_markup=pay("crypto", p)
    )
    await c.answer()

# ================== STARS ==================
@router.pre_checkout_query()
async def pre(q: PreCheckoutQuery):
    await q.answer(ok=True)

@router.message(F.successful_payment)
async def stars_ok(m: Message):
    payload = m.successful_payment.invoice_payload

    if payload.startswith("stars_"):
        plan = payload.split("_")[1]
        add_days(m.from_user.id, PLANS[plan]["days"])
        await give_access(m.from_user.id)

@router.callback_query(F.data.startswith("pay_stars_"))
async def pay_s(c: CallbackQuery):
    p = c.data.split("_")[2]
    d = PLANS[p]

    await bot.send_invoice(
        chat_id=c.message.chat.id,
        title="Подписка",
        description="Stars access",
        payload=f"stars_{p}",
        provider_token="",
        currency="XTR",
        prices=[LabeledPrice("access", d["stars"])]
    )

    await c.answer()

# ================== CRYPTO ==================
def create_invoice(amount, payload):
    url = "https://pay.crypt.bot/api/createInvoice"
    headers = {"Crypto-Pay-API-Token": CRYPTO_TOKEN}

    r = requests.post(url, headers=headers, json={
        "asset": "USDT",
        "amount": amount,
        "payload": payload
    })

    return r.json()["result"]

@router.callback_query(F.data.startswith("pay_crypto_"))
async def pay_c(c: CallbackQuery):
    p = c.data.split("_")[2]
    d = PLANS[p]

    invoice = create_invoice(d["crypto"], f"{c.from_user.id}:{p}")

    await c.message.answer(f"💰 Оплата:\n{invoice['pay_url']}")

    await c.answer()

# ================== CRYPTO WEBHOOK ==================
async def crypto_webhook(request):
    data = await request.json()

    if data.get("status") == "paid":
        payload = data.get("payload", "")
        user_id, plan = payload.split(":")

        user_id = int(user_id)

        add_days(user_id, PLANS[plan]["days"])
        await give_access(user_id)

    return web.Response(text="ok")

# ================== RUN ==================
async def main():
    asyncio.create_task(checker())

    app = web.Application()
    app.router.add_post("/crypto-webhook", crypto_webhook)

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", 8080)
    await site.start()

    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
