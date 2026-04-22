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

# ================== KEYBOARDS ==================
def back_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅ Назад", callback_data="back")]
    ])


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
    text = (
        "👋 Привет, я Ева и это мой закрытый канал\n\n"
        "❓ Что внутри?\n\n"
        "Закрытый контент по подписке\n"
        "💎 Без ограничений\n"
        "🔥 Обновления регулярно\n\n"
        "Выбери способ оплаты 👇"
    )

    await message.answer(text, reply_markup=menu())

# ================== BACK ==================
@router.callback_query(F.data == "back")
async def back(call: CallbackQuery):
    await call.message.edit_text("Главное меню 👇", reply_markup=menu())
    await call.answer()

# ================== MENU ==================
@router.callback_query(F.data == "stars")
async def stars(call: CallbackQuery):
    await call.message.edit_text("⭐ Выбери тариф", reply_markup=plans("stars"))
    await call.answer()


@router.callback_query(F.data == "crypto")
async def crypto(call: CallbackQuery):
    await call.message.edit_text("💰 Выбери тариф", reply_markup=plans("crypto"))
    await call.answer()

# ================== PLANS ==================
@router.callback_query(F.data.startswith("stars:"))
async def stars_plan(call: CallbackQuery):
    plan = call.data.split(":")[1]

    await call.message.edit_text(
        f"⭐ {plan} дней подписки\n\nНажми оплатить для продолжения",
        reply_markup=pay_kb("stars", plan)
    )
    await call.answer()


@router.callback_query(F.data.startswith("crypto:"))
async def crypto_plan(call: CallbackQuery):
    plan = call.data.split(":")[1]

    await call.message.edit_text(
        f"💰 {plan} дней подписки\n\nНажми оплатить для продолжения",
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
        "💡 Как получить +7 дней бесплатно:\n\n"
        "1️⃣ У тебя должна быть активная подписка\n"
        "2️⃣ Отправь свою ссылку другу\n"
        "3️⃣ Друг должен зайти и оформить подписку\n"
        "4️⃣ После этого ты получаешь +7 дней\n\n"
        "⚠️ Накрутка не засчитывается\n\n"
        f"🔗 Твоя ссылка:\n{link}\n\n"
        f"👤 Приглашено: {count} человек"
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

        if ref_id != user_id:
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

            # +7 days reward
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
                await bot.send_message(
                    ref_id,
                    "🎉 Новый друг зарегистрировался!\n+7 дней подписки начислено"
                )
            except:
                pass

# ================== RUN ==================
async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
