import asyncio
import logging
import os
import sqlite3
from datetime import datetime, timedelta

from aiogram import Bot, Dispatcher, F
from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    LabeledPrice
)
from aiogram.filters import Command
import aiohttp

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("bot")

# ================= ENV =================
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CRYPTO_TOKEN = os.getenv("CRYPTO_TOKEN")
GROUP_ID = os.getenv("TELEGRAM_GROUP_ID")

if not TOKEN:
    raise RuntimeError("TELEGRAM_BOT_TOKEN не задан")

bot = Bot(TOKEN)
dp = Dispatcher()

# ================= DB =================
conn = sqlite3.connect("users.db")
cur = conn.cursor()

cur.execute("""
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    expire TEXT
)
""")

cur.execute("""
CREATE TABLE IF NOT EXISTS payments (
    invoice_id TEXT,
    user_id INTEGER,
    days INTEGER,
    status TEXT
)
""")
conn.commit()

# ================= PRICES =================
STARS_PRICES = {1: 550, 7: 770, 30: 1100}
CRYPTO_PRICES = {1: 6.5, 7: 9, 30: 13}


# ================= UI =================
def main_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⭐ Stars", callback_data="stars")],
        [InlineKeyboardButton(text="💰 Crypto", callback_data="crypto")],
        [InlineKeyboardButton(text="🎁 Рефералка", callback_data="ref")],
        [InlineKeyboardButton(text="ℹ Информация", callback_data="info")]
    ])


def back_btn():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅ Назад", callback_data="back")]
    ])


# ================= START =================
@dp.message(Command("start"))
async def start(m: Message):
    await m.answer("Выбери оплату:", reply_markup=main_menu())


# ================= BACK =================
@dp.callback_query(F.data == "back")
async def back(c: CallbackQuery):
    await c.message.edit_text("Главное меню:", reply_markup=main_menu())
    await c.answer()


# ================= STARS =================
@dp.callback_query(F.data == "stars")
async def stars_menu(c: CallbackQuery):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="1 день", callback_data="s_1")],
        [InlineKeyboardButton(text="7 дней", callback_data="s_7")],
        [InlineKeyboardButton(text="30 дней", callback_data="s_30")],
        [InlineKeyboardButton(text="⬅ Назад", callback_data="back")]
    ])
    await c.message.edit_text("⭐ Stars оплата:", reply_markup=kb)
    await c.answer()


@dp.callback_query(F.data.startswith("s_"))
async def buy_stars(c: CallbackQuery):
    days = int(c.data.split("_")[1])
    price = STARS_PRICES[days]

    await bot.send_invoice(
        chat_id=c.message.chat.id,
        title=f"{days} days access",
        description="Premium access",
        payload=f"stars_{days}",
        provider_token="",
        currency="XTR",
        prices=[LabeledPrice(label="Access", amount=price)],
        start_parameter="stars"
    )
    await c.answer()


# ================= CRYPTO =================
async def create_invoice(amount, days):
    if not CRYPTO_TOKEN:
        raise Exception("CRYPTO_TOKEN не задан")

    url = "https://pay.crypt.bot/api/createInvoice"
    headers = {"Crypto-Pay-API-Token": CRYPTO_TOKEN}

    async with aiohttp.ClientSession() as session:
        async with session.post(url, json={
            "asset": "USDT",
            "amount": amount,
            "description": f"{days} days"
        }, headers=headers) as r:
            data = await r.json()

    if not data.get("ok"):
        raise Exception(data)

    result = data.get("result")
    if not result:
        raise Exception("no result from crypto API")

    return result


@dp.callback_query(F.data == "crypto")
async def crypto_menu(c: CallbackQuery):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="1 день", callback_data="c_1")],
        [InlineKeyboardButton(text="7 дней", callback_data="c_7")],
        [InlineKeyboardButton(text="30 дней", callback_data="c_30")],
        [InlineKeyboardButton(text="⬅ Назад", callback_data="back")]
    ])
    await c.message.edit_text("💰 Crypto оплата:", reply_markup=kb)
    await c.answer()


@dp.callback_query(F.data.startswith("c_"))
async def crypto_pay(c: CallbackQuery):
    days = int(c.data.split("_")[1])
    amount = CRYPTO_PRICES[days]

    try:
        inv = await create_invoice(amount, days)
    except Exception as e:
        log.error(e)
        await c.message.answer("❌ Crypto временно недоступен\nМожно оплатить через Stars ⭐")
        return

    invoice_id = inv.get("invoice_id")
    pay_url = inv.get("pay_url")

    if not invoice_id or not pay_url:
        await c.message.answer("Ошибка создания счёта")
        return

    cur.execute(
        "INSERT INTO payments VALUES (?, ?, ?, ?)",
        (invoice_id, c.from_user.id, days, "pending")
    )
    conn.commit()

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Я оплатил", callback_data=f"check_{invoice_id}")]
    ])

    await c.message.answer(pay_url, reply_markup=kb)
    await c.answer()


async def check_invoice(invoice_id: str):
    if not CRYPTO_TOKEN:
        return None

    url = "https://pay.crypt.bot/api/getInvoices"
    headers = {"Crypto-Pay-API-Token": CRYPTO_TOKEN}

    async with aiohttp.ClientSession() as session:
        async with session.get(url, params={"invoice_ids": invoice_id}, headers=headers) as r:
            data = await r.json()

    items = data.get("result", {}).get("items", [])
    if not items:
        return None

    return items[0].get("status")


@dp.callback_query(F.data.startswith("check_"))
async def check(c: CallbackQuery):
    invoice_id = c.data.split("_")[1]

    status = await check_invoice(invoice_id)

    if status != "paid":
        await c.message.answer("⏳ Не оплачено")
        return

    cur.execute("SELECT user_id, days FROM payments WHERE invoice_id=?", (invoice_id,))
    row = cur.fetchone()

    if not row:
        return

    user_id, days = row
    expire = datetime.now() + timedelta(days=days)

    cur.execute("INSERT OR REPLACE INTO users VALUES (?, ?)", (user_id, expire.isoformat()))
    conn.commit()

    await c.message.answer(f"✅ Доступ до {expire.date()}")


# ================= REF =================
@dp.callback_query(F.data == "ref")
async def ref(c: CallbackQuery):
    bot_info = await bot.get_me()
    link = f"https://t.me/{bot_info.username}?start={c.from_user.id}"

    await c.message.edit_text(
        f"🎁 Рефералка:\n{link}",
        reply_markup=back_btn()
    )


# ================= INFO =================
@dp.callback_query(F.data == "info")
async def info(c: CallbackQuery):
    await c.message.edit_text(
        "ℹ Бот подписки с оплатой Stars и Crypto.",
        reply_markup=back_btn()
    )


# ================= RUN =================
async def main():
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
