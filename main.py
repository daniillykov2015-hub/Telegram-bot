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
)

# ================== CONFIG ==================
logging.basicConfig(level=logging.INFO)

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CRYPTO_TOKEN = os.getenv("CRYPTO_TOKEN")

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

# 🆕 рефералы
cursor.execute("""
CREATE TABLE IF NOT EXISTS referrals (
    user_id INTEGER,
    referred_id INTEGER UNIQUE
)
""")

conn.commit()

# ================== CACHE ==================
active_invoices = {}

# ================== PLANS ==================
PLANS = {
    "1": {"days": 1, "stars": 550, "crypto": 5},
    "7": {"days": 7, "stars": 770, "crypto": 7},
    "30": {"days": 30, "stars": 1100, "crypto": 10},
}

# ================== SAFE UI ==================
async def safe_update(call: CallbackQuery, text: str | None = None, markup=None):
    try:
        if text:
            await call.message.edit_text(text, reply_markup=markup)
        else:
            await call.message.edit_reply_markup(reply_markup=markup)
    except:
        pass
    await call.answer()

# ================== KEYBOARDS ==================
def menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="⭐ Stars", callback_data="stars"),
            InlineKeyboardButton(text="💰 Crypto", callback_data="crypto"),
        ],
        [
            InlineKeyboardButton(text="👥 Реф система", callback_data="ref")
        ]
    ])


def plans(prefix):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="1 день", callback_data=f"{prefix}:1")],
        [InlineKeyboardButton(text="7 дней", callback_data=f"{prefix}:7")],
        [InlineKeyboardButton(text="30 дней", callback_data=f"{prefix}:30")],
        [InlineKeyboardButton(text="⬅ Назад", callback_data="back")]
    ])


def pay(prefix, plan):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💳 Оплатить", callback_data=f"pay:{prefix}:{plan}")],
        [InlineKeyboardButton(text="⬅ Назад", callback_data="back")]
    ])

# ================== START ==================
@router.message(CommandStart())
async def start(message: Message):
    text = (
        "👋 Привет, я Ева и это мой закрытый канал\n\n"
        "❓ Что внутри?\n\n"
        "Закрытый контент по подписке\n\n"
        "💎 Без ограничений\n"
        "🔥 Обновления регулярно\n\n"
        "Выбери способ оплаты 👇"
    )

    await message.answer(text, reply_markup=menu())

# ================== REF SYSTEM ==================
@router.callback_query(F.data == "ref")
async def ref(call: CallbackQuery):
    user_id = call.from_user.id

    link = f"https://t.me/{(await bot.get_me()).username}?start={user_id}"

    cursor.execute(
        "SELECT COUNT(*) FROM referrals WHERE user_id=?",
        (user_id,)
    )
    count = cursor.fetchone()[0]

    await safe_update(
        call,
        f"👥 Реферальная система\n\n"
        f"Твоя ссылка:\n{link}\n\n"
        f"Приведено друзей: {count}\n"
        f"Бонус: +7 дней за каждого друга"
    )

# ================== REF LOGIC ==================
@router.message(CommandStart(deep_link=True))
async def referral_start(message: Message):
    args = message.text.split()

    if len(args) > 1:
        ref_id = int(args[1])
        user_id = message.from_user.id

        if ref_id != user_id:
            cursor.execute(
                "SELECT 1 FROM referrals WHERE referred_id=?",
                (user_id,)
            )
            already = cursor.fetchone()

            if not already:
                cursor.execute(
                    "INSERT INTO referrals VALUES (?, ?)",
                    (ref_id, user_id)
                )
                conn.commit()

                # +7 дней рефереру
                cursor.execute(
                    "SELECT expire_date FROM users WHERE user_id=?",
                    (ref_id,)
                )
                row = cursor.fetchone()

                now = datetime.utcnow()
                bonus = timedelta(days=7)

                if row and row[0]:
                    exp = datetime.fromisoformat(row[0])
                    new_exp = exp + bonus if exp > now else now + bonus
                else:
                    new_exp = now + bonus

                cursor.execute(
                    "INSERT OR REPLACE INTO users VALUES (?, ?)",
                    (ref_id, new_exp.isoformat())
                )
                conn.commit()

                try:
                    await bot.send_message(
                        ref_id,
                        "🎉 У тебя новый друг!\n+7 дней к подписке начислено"
                    )
                except:
                    pass

# ================== NAV ==================
@router.callback_query(F.data == "back")
async def back(call: CallbackQuery):
    await safe_update(call, "Меню", menu())


@router.callback_query(F.data == "stars")
async def stars(call: CallbackQuery):
    await safe_update(call, "⭐ Тарифы", plans("stars"))


@router.callback_query(F.data == "crypto")
async def crypto(call: CallbackQuery):
    await safe_update(call, "💰 Тарифы", plans("crypto"))

# ================== PLANS ==================
@router.callback_query(F.data.startswith("stars:"))
async def stars_plan(call: CallbackQuery):
    plan = call.data.split(":")[1]
    await safe_update(call, f"{plan} дней — {PLANS[plan]['stars']}⭐", pay("stars", plan))


@router.callback_query(F.data.startswith("crypto:"))
async def crypto_plan(call: CallbackQuery):
    plan = call.data.split(":")[1]
    await safe_update(call, f"{plan} дней — {PLANS[plan]['crypto']} USDT", pay("crypto", plan))

# ================== RUN ==================
async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
