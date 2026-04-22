import asyncio
import logging
import os
import sqlite3
from datetime import datetime, timedelta

import requests

from aiogram import Bot, Dispatcher, Router, F
from aiogram.filters import CommandStart, Command
from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    LabeledPrice,
    PreCheckoutQuery,
    ChatMember,
    ChatInviteLink
)

# ================== CONFIG ==================
logging.basicConfig(level=logging.INFO)

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CRYPTO_TOKEN = os.getenv("CRYPTO_TOKEN")
CHANNEL_ID = int(os.getenv("TELEGRAM_GROUP_ID", "0"))
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))

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
    if text:
        await call.message.edit_text(text, reply_markup=markup)
    else:
        await call.message.edit_reply_markup(reply_markup=markup)
    await call.answer()

# ================== HELPERS ==================
async def is_user_in_channel(user_id: int) -> bool:
    try:
        member: ChatMember = await bot.get_chat_member(CHANNEL_ID, user_id)
        return member.status in ("member", "administrator", "creator")
    except:
        return False


async def create_secure_invite():
    expire_date = datetime.utcnow() + timedelta(minutes=10)
    invite: ChatInviteLink = await bot.create_chat_invite_link(
        chat_id=CHANNEL_ID,
        member_limit=1,
        expire_date=expire_date
    )
    return invite.invite_link


# ================== ACCESS ==================
async def grant_access(user_id: int, days: int):
    now = datetime.utcnow()

    cursor.execute("SELECT expire_date FROM users WHERE user_id=?", (user_id,))
    row = cursor.fetchone()

    if row and row[0]:
        current = datetime.fromisoformat(row[0])
        new_expire = current + timedelta(days=days) if current > now else now + timedelta(days=days)
    else:
        new_expire = now + timedelta(days=days)

    cursor.execute(
        "INSERT OR REPLACE INTO users VALUES (?, ?)",
        (user_id, new_expire.isoformat())
    )
    conn.commit()

    if await is_user_in_channel(user_id):
        text = f"✅ Подписка продлена до:\n{new_expire.strftime('%Y-%m-%d %H:%M')}\n\nТы уже в канале 👍"
    else:
        link = await create_secure_invite()
        text = f"✅ Доступ до:\n{new_expire.strftime('%Y-%m-%d %H:%M')}\n\n👉 Вход (10 минут):\n{link}"

    try:
        await bot.send_message(user_id, text)
    except:
        pass

    active_invoices.pop(user_id, None)


# ================== AUTO CLEAN ==================
async def remove_expired_users():
    while True:
        try:
            now = datetime.utcnow()

            cursor.execute("SELECT user_id, expire_date FROM users")
            rows = cursor.fetchall()

            for user_id, exp in rows:
                if not exp:
                    continue

                if datetime.fromisoformat(exp) < now:
                    try:
                        member = await bot.get_chat_member(CHANNEL_ID, user_id)
                        if member.status in ("member", "administrator", "creator"):
                            await bot.ban_chat_member(CHANNEL_ID, user_id)
                            await bot.unban_chat_member(CHANNEL_ID, user_id)
                    except:
                        pass

            await asyncio.sleep(1800)

        except Exception as e:
            logging.error(f"remove_expired_users error: {e}")
            await asyncio.sleep(60)


# ================== KEYBOARDS ==================
def menu(active=False):
    kb = [
        [
            InlineKeyboardButton(text="⭐ Stars", callback_data="stars"),
            InlineKeyboardButton(text="💰 Crypto", callback_data="crypto"),
        ]
    ]

    if active:
        kb.append([InlineKeyboardButton(text="🔁 Продлить", callback_data="renew")])

    return InlineKeyboardMarkup(inline_keyboard=kb)


def plans(prefix):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="1 день", callback_data=f"{prefix}_1")],
        [InlineKeyboardButton(text="7 дней", callback_data=f"{prefix}_7")],
        [InlineKeyboardButton(text="30 дней", callback_data=f"{prefix}_30")],
        [InlineKeyboardButton(text="⬅ Назад", callback_data="back")]
    ])


def pay(prefix, plan):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💳 Оплатить", callback_data=f"pay_{prefix}_{plan}")],
        [InlineKeyboardButton(text="⬅ Назад", callback_data=prefix)]
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


@router.callback_query(F.data == "renew")
async def renew(call: CallbackQuery):
    await safe_update(call, "🔁 Продлить:", plans("crypto"))


# ================== PLANS ==================
@router.callback_query(F.data.startswith("stars_"))
async def stars_plan(call: CallbackQuery):
    p = call.data.split("_")[1]
    await safe_update(call, f"{p} дней — {PLANS[p]['stars']}⭐", pay("stars", p))


@router.callback_query(F.data.startswith("crypto_"))
async def crypto_plan(call: CallbackQuery):
    p = call.data.split("_")[1]
    await safe_update(call, f"{p} дней — {PLANS[p]['crypto']} USDT", pay("crypto", p))


# ================== RUN ==================
async def main():
    asyncio.create_task(remove_expired_users())
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
