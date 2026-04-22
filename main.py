import asyncio
import logging
import os
import sqlite3
from datetime import datetime, timedelta

import requests
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

# ---------------- CONFIG ----------------
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
GROUP_ID = int(os.getenv("TELEGRAM_GROUP_ID", "0"))
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))

logging.basicConfig(level=logging.INFO)

bot = Bot(TOKEN)
dp = Dispatcher()

# ---------------- DB ----------------
conn = sqlite3.connect("users.db")
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    expire_date TEXT,
    ref_by INTEGER
)
""")

conn.commit()

# ---------------- UTIL ----------------
def parse_args(message: types.Message) -> str:
    """
    SAFE ARG PARSER (v3 replacement for get_args)
    """
    text = message.text or ""
    parts = text.split(maxsplit=1)
    return parts[1] if len(parts) > 1 else ""


def get_expire(user_id: int):
    cursor.execute("SELECT expire_date FROM users WHERE user_id=?", (user_id,))
    row = cursor.fetchone()

    if row and row[0]:
        try:
            return datetime.fromisoformat(row[0])
        except:
            return None
    return None


def set_expire(user_id: int, days: int):
    expire = datetime.now() + timedelta(days=days)

    cursor.execute("""
    INSERT INTO users (user_id, expire_date)
    VALUES (?, ?)
    ON CONFLICT(user_id)
    DO UPDATE SET expire_date=excluded.expire_date
    """, (user_id, expire.isoformat()))

    conn.commit()
    return expire


# ---------------- KEYBOARD ----------------
def main_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📅 Подписка", callback_data="sub")],
        [InlineKeyboardButton(text="🎁 Рефералка", callback_data="ref")],
        [InlineKeyboardButton(text="ℹ️ Инфо", callback_data="info")]
    ])


# ---------------- START ----------------
@dp.message(Command("start"))
async def start(message: types.Message):
    args = parse_args(message)

    # referral
    if args.isdigit():
        ref_id = int(args)
        if ref_id != message.from_user.id:
            cursor.execute("SELECT user_id FROM users WHERE user_id=?", (message.from_user.id,))
            if not cursor.fetchone():
                cursor.execute(
                    "INSERT INTO users (user_id, ref_by) VALUES (?, ?)",
                    (message.from_user.id, ref_id)
                )
                conn.commit()

    await message.answer(
        "🔥 STABLE CORE v3\n\nВыбери действие:",
        reply_markup=main_kb()
    )


# ---------------- CALLBACKS ----------------
@dp.callback_query()
async def router(call: types.CallbackQuery):
    await call.answer()
    data = call.data

    # BACK / INFO
    if data == "info":
        await call.message.edit_text(
            "ℹ️ Это стабильный core бот v3.\nБез падений и старых багов.",
            reply_markup=main_kb()
        )

    elif data == "ref":
        link = f"https://t.me/{(await bot.get_me()).username}?start={call.from_user.id}"
        await call.message.edit_text(
            f"🎁 Реферальная ссылка:\n{link}",
            reply_markup=main_kb()
        )

    elif data == "sub":
        exp = get_expire(call.from_user.id)

        if not exp:
            text = "❌ Подписка отсутствует"
        elif exp < datetime.now():
            text = "❌ Подписка истекла"
        else:
            text = f"✅ Активна до: {exp.strftime('%d.%m.%Y %H:%M')}"

        await call.message.edit_text(text, reply_markup=main_kb())

    elif data == "buy_1":
        expire = set_expire(call.from_user.id, 1)

        await call.message.edit_text(
            f"✅ Подписка активирована\nДо: {expire.strftime('%d.%m.%Y')}",
            reply_markup=main_kb()
        )


# ---------------- ADMIN ----------------
@dp.message(Command("users"))
async def users(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        return

    cursor.execute("SELECT COUNT(*) FROM users")
    count = cursor.fetchone()[0]

    await message.answer(f"👥 Users: {count}")


# ---------------- SAFE CRYPTO (stub) ----------------
async def crypto_checker():
    """
    SAFE LOOP (no crash)
    """
    while True:
        try:
            # сюда потом подключим CryptoBot API
            pass
        except Exception as e:
            logging.warning(f"crypto loop error: {e}")

        await asyncio.sleep(30)


# ---------------- SUB CHECK ----------------
async def sub_checker():
    while True:
        try:
            now = datetime.now()

            cursor.execute("SELECT user_id, expire_date FROM users")
            rows = cursor.fetchall()

            for uid, exp in rows:
                if not exp:
                    continue

                try:
                    if datetime.fromisoformat(exp) < now:
                        await bot.send_message(uid, "❌ Подписка истекла")
                except:
                    pass

        except Exception as e:
            logging.warning(f"sub checker error: {e}")

        await asyncio.sleep(300)


# ---------------- STARTUP ----------------
async def main():
    logging.info("BOT STARTED (STABLE CORE v3)")

    asyncio.create_task(sub_checker())
    asyncio.create_task(crypto_checker())

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
