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
STARS = {1: 550, 7: 770, 30: 1100}
CRYPTO = {1: 6.5, 7: 9, 30: 13}

# ================= UI =================
def menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⭐ Stars", callback_data="stars")],
        [InlineKeyboardButton(text="💰 Crypto", callback_data="crypto")],
        [InlineKeyboardButton(text="🎁 Рефералка", callback_data="ref")],
        [InlineKeyboardButton(text="ℹ Инфо", callback_data="info")]
    ])

def back():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅ Назад", callback_data="back")]
    ])

# ================= START =================
@dp.message(Command("start"))
async def start(m: Message):
    await m.answer(
        "🔐 Добро пожаловать\n\nВыбери способ оплаты:",
        reply_markup=menu()
    )

# ================= BACK =================
@dp.callback_query(F.data == "back")
async def back_handler(c: CallbackQuery):
    await c.message.edit_text("Главное меню:", reply_markup=menu())
    await c.answer()

# ================= STARS =================
@dp.callback_query(F.data == "stars")
async def stars(c: CallbackQuery):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="1 день", callback_data="s_1")],
        [InlineKeyboardButton(text="7 дней", callback_data="s_7")],
        [InlineKeyboardButton(text="30 дней", callback_data="s_30")],
        [InlineKeyboardButton(text="⬅ Назад", callback_data="back")]
    ])

    await c.message.edit_text("⭐ Оплата Stars:", reply_markup=kb)
    await c.answer()

@dp.callback_query(F.data.startswith("s_"))
async def buy_stars(c: CallbackQuery):
    days = int(c.data.split("_")[1])

    await bot.send_invoice(
        chat_id=c.message.chat.id,
        title=f"{days} дней доступа",
        description="Premium доступ",
        payload=f"stars_{days}",
        provider_token="",
        currency="XTR",
        prices=[LabeledPrice(label="Access", amount=STARS[days]),
    )

    await c.answer()

@dp.message(F.successful_payment)
async def paid(m: Message):
    payload = m.successful_payment.invoice_payload
    days = int(payload.split("_")[1])

    expire = datetime.now() + timedelta(days=days)

    cur.execute("INSERT OR REPLACE INTO users VALUES (?, ?)",
                (m.from_user.id, expire.isoformat()))
    conn.commit()

    await m.answer(f"✅ Оплата прошла\nДоступ до {expire.date()}")

# ================= CRYPTO =================
async def create_invoice(amount, days):
    if not CRYPTO_TOKEN:
        return None

    url = "https://pay.crypt.bot/api/createInvoice"
    headers = {"Crypto-Pay-API-Token": CRYPTO_TOKEN}

    async with aiohttp.ClientSession() as s:
        async with s.post(url, json={
            "asset": "USDT",
            "amount": amount,
            "description": f"{days} days"
        }, headers=headers) as r:
            data = await r.json()

    if not data.get("ok"):
        return None

    return data["result"]

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
    if not CRYPTO_TOKEN:
        await c.message.answer("❌ Crypto не настроен в Railway ENV")
        return

    days = int(c.data.split("_")[1])
    amount = CRYPTO[days]

    invoice = await create_invoice(amount, days)

    if not invoice:
        await c.message.answer("❌ Crypto временно недоступен")
        return

    pay_url = invoice["pay_url"]

    await c.message.answer(f"💳 Оплати:\n{pay_url}")
    await c.answer()

# ================= REF =================
@dp.callback_query(F.data == "ref")
async def ref(c: CallbackQuery):
    bot_info = await bot.get_me()
    link = f"https://t.me/{bot_info.username}?start={c.from_user.id}"

    await c.message.edit_text(
        f"🎁 Реферальная ссылка:\n{link}",
        reply_markup=back()
    )
    await c.answer()

# ================= INFO =================
@dp.callback_query(F.data == "info")
async def info(c: CallbackQuery):
    await c.message.edit_text(
        "ℹ Бот подписки\n\n⭐ Stars / 💰 Crypto\n🔐 Автодоступ после оплаты",
        reply_markup=back()
    )
    await c.answer()

# ================= RUN =================
async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
