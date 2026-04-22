import asyncio
import logging
import os
import sqlite3
from datetime import datetime, timedelta

from aiogram import Bot, Dispatcher, Router, F
from aiogram.filters import CommandStart
from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)

# ================== CONFIG ==================
logging.basicConfig(level=logging.INFO)

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

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
CREATE TABLE IF NOT EXISTS referrals (
    user_id INTEGER,
    referred_id INTEGER UNIQUE
)
""")

conn.commit()

# ================== MAIN TEXT ==================
MAIN_TEXT = (
    "👋 Привет, я Ева и это мой закрытый канал\n\n"
    "❓ Что внутри?\n\n"
    "Закрытый контент по подписке\n"
    "💎 Без ограничений\n"
    "🔥 Обновления регулярно\n\n"
    "Выбери способ оплаты 👇"
)

# ================== KEYBOARDS ==================
def menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="⭐ Stars", callback_data="stars"),
            InlineKeyboardButton(text="💰 Crypto", callback_data="crypto"),
        ],
        [
            InlineKeyboardButton(text="👥 Реферальная система", callback_data="ref")
        ]
    ])


def back_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅ Назад", callback_data="back")]
    ])


def plans(prefix):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="1 день", callback_data=f"{prefix}:1")],
        [InlineKeyboardButton(text="7 дней", callback_data=f"{prefix}:7")],
        [InlineKeyboardButton(text="30 дней", callback_data=f"{prefix}:30")],
        [InlineKeyboardButton(text="⬅ Назад", callback_data="back")]
    ])


def pay_kb(prefix, plan):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💳 Оплатить", callback_data=f"pay:{prefix}:{plan}")],
        [InlineKeyboardButton(text="⬅ Назад", callback_data=f"{prefix}")]
    ])

# ================== START ==================
@router.message(CommandStart())
async def start(message: Message):
    await message.answer(MAIN_TEXT, reply_markup=menu())

# ================== SAFE NAV (НЕ ЛОМАЕТ ТЕКСТ) ==================
async def swap_keyboard(call: CallbackQuery, markup):
    await call.message.edit_reply_markup(reply_markup=markup)
    await call.answer()

# ================== BACK ==================
@router.callback_query(F.data == "back")
async def back(call: CallbackQuery):
    await swap_keyboard(call, menu())

# ================== MENU ==================
@router.callback_query(F.data == "stars")
async def stars(call: CallbackQuery):
    await swap_keyboard(call, plans("stars"))


@router.callback_query(F.data == "crypto")
async def crypto(call: CallbackQuery):
    await swap_keyboard(call, plans("crypto"))

# ================== PLANS ==================
@router.callback_query(F.data.startswith("stars:"))
async def stars_plan(call: CallbackQuery):
    plan = call.data.split(":")[1]

    await call.message.edit_reply_markup(
        reply_markup=pay_kb("stars", plan)
    )
    await call.answer()


@router.callback_query(F.data.startswith("crypto:"))
async def crypto_plan(call: CallbackQuery):
    plan = call.data.split(":")[1]

    await call.message.edit_reply_markup(
        reply_markup=pay_kb("crypto", plan)
    )
    await call.answer()

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

    text = (
        "👥 РЕФЕРАЛЬНАЯ СИСТЕМА\n\n"
        "💡 Как получить +7 дней:\n"
        "1️⃣ У тебя должна быть подписка\n"
        "2️⃣ Пригласи друга по ссылке\n"
        "3️⃣ Он оформляет доступ\n"
        "4️⃣ Ты получаешь +7 дней\n\n"
        f"🔗 Ссылка:\n{link}\n\n"
        f"👤 Приглашено: {count}"
    )

    await call.message.edit_text(text, reply_markup=back_kb())
    await call.answer()

# ================== REF LOGIC ==================
@router.message(CommandStart(deep_link=True))
async def referral_start(message: Message):
    args = message.text.split()

    if len(args) > 1:
        ref_id = int(args[1])
        user_id = message.from_user.id

        if ref_id == user_id:
            return

        cursor.execute(
            "SELECT 1 FROM referrals WHERE referred_id=?",
            (user_id,)
        )
        if cursor.fetchone():
            return

        cursor.execute(
            "INSERT INTO referrals VALUES (?, ?)",
            (ref_id, user_id)
        )
        conn.commit()

        now = datetime.utcnow()
        cursor.execute("SELECT expire_date FROM users WHERE user_id=?", (ref_id,))
        row = cursor.fetchone()

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
            await bot.send_message(ref_id, "🎉 +7 дней за нового друга!")
        except:
            pass

# ================== RUN ==================
async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
