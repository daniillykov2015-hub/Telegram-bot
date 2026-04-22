import asyncio
import logging
import os
import sqlite3
from datetime import datetime, timedelta

import requests
from aiogram import Bot, Dispatcher, types, F
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
from aiogram.enums import ContentType

logging.basicConfig(level=logging.INFO)

API_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
GROUP_ID = os.getenv("TELEGRAM_GROUP_ID")
CRYPTO_TOKEN = os.getenv("CRYPTO_TOKEN")

bot = Bot(token=API_TOKEN)
dp = Dispatcher()


# --- DB ---
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


# --- CRYPTO ---
def create_invoice(amount, payload):
    url = "https://pay.crypt.bot/api/createInvoice"
    headers = {"Crypto-Pay-API-Token": CRYPTO_TOKEN}

    r = requests.post(url, headers=headers, json={
        "asset": "USDT",
        "amount": amount,
        "description": payload
    })

    return r.json()["result"]


def check_invoice(invoice_id):
    url = "https://pay.crypt.bot/api/getInvoices"
    headers = {"Crypto-Pay-API-Token": CRYPTO_TOKEN}

    r = requests.get(url, headers=headers, params={
        "invoice_ids": invoice_id
    })

    return r.json()["result"]["items"][0]["status"]


# --- UI ---
def main_kb():
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💰 Crypto", callback_data="crypto")],
        [InlineKeyboardButton(text="📅 Подписка", callback_data="sub")]
    ])
    return kb


# --- START ---
@dp.message(Command("start"))
async def start(msg: types.Message):
    await msg.answer("Добро пожаловать", reply_markup=main_kb())


# --- CRYPTO MENU ---
@dp.callback_query(F.data == "crypto")
async def crypto_menu(call: types.CallbackQuery):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="1 день", callback_data="c1")],
        [InlineKeyboardButton(text="7 дней", callback_data="c7")],
        [InlineKeyboardButton(text="30 дней", callback_data="c30")]
    ])
    await call.message.answer("Выбери тариф:", reply_markup=kb)


# --- CREATE INVOICE ---
@dp.callback_query(F.data.in_(["c1", "c7", "c30"]))
async def crypto_pay(call: types.CallbackQuery):
    mapping = {
        "c1": (5, 1),
        "c7": (7, 7),
        "c30": (10, 30)
    }

    amount, days = mapping[call.data]

    invoice = create_invoice(amount, f"{days}_days")

    cursor.execute(
        "INSERT INTO payments VALUES (?, ?, ?, ?)",
        (invoice["invoice_id"], call.from_user.id, days, "pending")
    )
    conn.commit()

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Проверить оплату", callback_data="check")]
    ])

    await call.message.answer(invoice["pay_url"], reply_markup=kb)


# --- CHECK PAYMENT ---
@dp.callback_query(F.data == "check")
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
        "INSERT OR REPLACE INTO users VALUES (?, ?)",
        (call.from_user.id, expire.isoformat())
    )
    conn.commit()

    invite = await bot.create_chat_invite_link(GROUP_ID, member_limit=1)

    await call.message.answer(f"Доступ до {expire.date()}\n{invite.invite_link}")


# --- SUB ---
@dp.callback_query(F.data == "sub")
async def sub(call: types.CallbackQuery):
    cursor.execute(
        "SELECT expire_date FROM users WHERE user_id=?",
        (call.from_user.id,)
    )
    row = cursor.fetchone()

    if not row:
        await call.message.answer("Нет подписки")
        return

    await call.message.answer(f"До: {row[0]}")


# --- AUTO CHECK ---
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


# --- MAIN ---
async def main():
    if not API_TOKEN or not GROUP_ID:
        print("Нет ENV")
        return

    asyncio.create_task(sub_checker())
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
