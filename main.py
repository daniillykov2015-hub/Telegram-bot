import asyncio
import logging
import os
import requests
import sqlite3
import time
from datetime import datetime, timedelta

from aiogram import Bot, Dispatcher, types, executor
from aiogram.types import (
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    ContentType,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

API_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
GROUP_ID = os.getenv("TELEGRAM_GROUP_ID")
CRYPTO_TOKEN = os.getenv("CRYPTO_TOKEN")
ADMIN_ID = os.getenv("ADMIN_ID")

try:
    ADMIN_ID = int(ADMIN_ID) if ADMIN_ID else None
except:
    ADMIN_ID = None


def is_admin(user_id: int) -> bool:
    return ADMIN_ID and user_id == ADMIN_ID


# --- BOT ---
bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot)


# --- DB ---
conn = sqlite3.connect("users.db")
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    expire_date TEXT,
    ref_by INTEGER,
    refs_paid INTEGER DEFAULT 0,
    notified INTEGER DEFAULT 0,
    ref_bonus_paid INTEGER DEFAULT 0
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
CREATE TABLE IF NOT EXISTS payments_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    method TEXT,
    days INTEGER,
    amount REAL,
    currency TEXT,
    created_at TEXT
)
""")

conn.commit()


# --- LOG ---
def log_payment(user_id, method, days, amount, currency):
    cursor.execute(
        "INSERT INTO payments_log (user_id, method, days, amount, currency, created_at) VALUES (?, ?, ?, ?, ?, ?)",
        (user_id, method, days, amount, currency, datetime.now().isoformat())
    )
    conn.commit()


# --- CRYPTO ---
class CryptoPayError(Exception):
    pass


def create_invoice(amount, payload):
    url = "https://pay.crypt.bot/api/createInvoice"
    headers = {"Crypto-Pay-API-Token": CRYPTO_TOKEN}

    r = requests.post(url, headers=headers, json={
        "asset": "USDT",
        "amount": amount,
        "description": payload
    }, timeout=15)

    data = r.json()

    if not data.get("ok"):
        raise CryptoPayError(data)

    return data["result"]


def check_invoice(invoice_id):
    url = "https://pay.crypt.bot/api/getInvoices"
    headers = {"Crypto-Pay-API-Token": CRYPTO_TOKEN}

    r = requests.get(url, headers=headers, params={
        "invoice_ids": invoice_id
    }, timeout=15)

    data = r.json()

    if not data.get("ok"):
        raise CryptoPayError(data)

    return data["result"]["items"][0]["status"]


# --- COOLDOWN ---
last_invoice = {}

def cooldown(user_id):
    now = time.time()
    last = last_invoice.get(user_id, 0)

    if now - last < 60:
        return int(60 - (now - last))

    return 0


def mark(user_id):
    last_invoice[user_id] = time.time()


# --- UI ---
def main_kb():
    kb = InlineKeyboardMarkup()
    kb.add(
        InlineKeyboardButton("⭐ Stars", callback_data="stars"),
        InlineKeyboardButton("💰 Crypto", callback_data="crypto"),
    )
    kb.add(
        InlineKeyboardButton("🎁 Реферал", callback_data="ref"),
        InlineKeyboardButton("📅 Подписка", callback_data="sub"),
    )
    return kb


# --- START ---
@dp.message_handler(commands=["start"])
async def start(msg: types.Message):
    await msg.answer("Добро пожаловать", reply_markup=main_kb())


# --- CRYPTO ---
@dp.callback_query_handler(lambda c: c.data == "crypto")
async def crypto(call: types.CallbackQuery):
    kb = InlineKeyboardMarkup()
    kb.add(
        InlineKeyboardButton("1 день", callback_data="c1"),
        InlineKeyboardButton("7 дней", callback_data="c7"),
        InlineKeyboardButton("30 дней", callback_data="c30"),
    )
    await call.message.answer("Выбери тариф:", reply_markup=kb)


@dp.callback_query_handler(lambda c: c.data.startswith("c"))
async def crypto_pay(call: types.CallbackQuery):
    mapping = {"c1": (5, 1), "c7": (7, 7), "c30": (10, 30)}
    amount, days = mapping[call.data]

    cd = cooldown(call.from_user.id)
    if cd:
        await call.answer(f"Подожди {cd} сек", show_alert=True)
        return

    inv = create_invoice(amount, f"{days}_days")

    cursor.execute(
        "INSERT INTO payments VALUES (?, ?, ?, ?)",
        (inv["invoice_id"], call.from_user.id, days, "pending")
    )
    conn.commit()

    mark(call.from_user.id)

    kb = InlineKeyboardMarkup().add(
        InlineKeyboardButton("Проверить оплату", callback_data="check")
    )

    await call.message.answer(inv["pay_url"], reply_markup=kb)


@dp.callback_query_handler(lambda c: c.data == "check")
async def check(call: types.CallbackQuery):
    cursor.execute(
        "SELECT invoice_id, days FROM payments WHERE user_id=? ORDER BY rowid DESC LIMIT 1",
        (call.from_user.id,)
    )
    row = cursor.fetchone()

    if not row:
        await call.message.answer("Нет счета")
        return

    invoice_id, days = row

    status = check_invoice(invoice_id)

    if status != "paid":
        await call.message.answer("Не оплачено")
        return

    expire = datetime.now() + timedelta(days=days)

    cursor.execute(
        "INSERT OR REPLACE INTO users (user_id, expire_date, notified) VALUES (?, ?, 0)",
        (call.from_user.id, expire.isoformat())
    )

    log_payment(call.from_user.id, "crypto", days, days, "USDT")

    conn.commit()

    invite = await bot.create_chat_invite_link(GROUP_ID, member_limit=1)

    await call.message.answer(f"Доступ до {expire.date()}\n{invite.invite_link}")


# --- STARS ---
@dp.callback_query_handler(lambda c: c.data == "stars")
async def stars(call: types.CallbackQuery):
    await bot.send_invoice(
        chat_id=call.from_user.id,
        title="Доступ",
        description="Подписка",
        payload="stars_1",
        provider_token="",
        currency="XTR",
        prices=[types.LabeledPrice(label="1 день", amount=550)]
    )


@dp.pre_checkout_query_handler(lambda q: True)
async def checkout(q: types.PreCheckoutQuery):
    await bot.answer_pre_checkout_query(q.id, ok=True)


@dp.message_handler(content_types=ContentType.SUCCESSFUL_PAYMENT)
async def success(msg: types.Message):
    expire = datetime.now() + timedelta(days=1)

    cursor.execute(
        "INSERT OR REPLACE INTO users (user_id, expire_date, notified) VALUES (?, ?, 0)",
        (msg.from_user.id, expire.isoformat())
    )

    log_payment(msg.from_user.id, "stars", 1, 550, "XTR")

    conn.commit()

    invite = await bot.create_chat_invite_link(GROUP_ID, member_limit=1)

    await msg.answer(f"Оплачено\n{invite.invite_link}")


# --- SUB CHECK ---
async def sub_checker():
    while True:
        now = datetime.now()

        cursor.execute("SELECT user_id, expire_date FROM users")
        for uid, exp in cursor.fetchall():
            if exp and datetime.fromisoformat(exp) < now:
                try:
                    await bot.ban_chat_member(GROUP_ID, uid)
                    await bot.unban_chat_member(GROUP_ID, uid)
                except:
                    pass

        await asyncio.sleep(60)


# --- STARTUP ---
async def on_startup(dp):
    asyncio.create_task(sub_checker())


# --- RUN ---
if __name__ == "__main__":
    if not API_TOKEN or not GROUP_ID:
        logger.error("Нет ENV")
        exit(1)

    executor.start_polling(dp, skip_updates=True, on_startup=on_startup)
