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
        text = (
            f"✅ Подписка продлена до:\n{new_expire.strftime('%Y-%m-%d %H:%M')}\n\n"
            f"Ты уже в канале 👍"
        )
    else:
        link = await create_secure_invite()
        text = (
            f"✅ Доступ до:\n{new_expire.strftime('%Y-%m-%d %H:%M')}\n\n"
            f"👉 Вход (10 минут):\n{link}"
        )

    try:
        await bot.send_message(user_id, text)
    except:
        pass

    active_invoices.pop(user_id, None)


# ================== AUTO REMOVE ==================
async def remove_expired_users():
    while True:
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


# ================== START (ОБНОВЛЕНО ТОЛЬКО ТУТ) ==================
@router.message(CommandStart())
async def start(message: Message):
    user_id = message.from_user.id

    cursor.execute("SELECT expire_date FROM users WHERE user_id=?", (user_id,))
    row = cursor.fetchone()

    if row and row[0]:
        expire = datetime.fromisoformat(row[0])

        if expire > datetime.utcnow():
            if await is_user_in_channel(user_id):
                await message.answer(
                    f"👋 Подписка активна до:\n{expire.strftime('%Y-%m-%d %H:%M')}\n\nТы уже в канале 👍",
                    reply_markup=menu(active=True)
                )
            else:
                link = await create_secure_invite()
                await message.answer(
                    f"👋 Подписка активна до:\n{expire.strftime('%Y-%m-%d %H:%M')}\n\n"
                    f"👉 Войти (10 минут):\n{link}",
                    reply_markup=menu(active=True)
                )
            return

    await message.answer(
        "👋 Привет, я Ева и это мой закрытый канал\n\n"
        "❓ Что внутри?\n\n"
        "Закрытый контент по подписке\n\n"
        "💎 Без ограничений\n"
        "🔥 Обновления регулярно\n\n"
        "Выбери способ оплаты 👇",
        reply_markup=menu()
    )


# ================== HISTORY ==================
@router.message(Command("history"))
async def history(message: Message):
    cursor.execute(
        "SELECT days, status FROM payments WHERE user_id=? ORDER BY rowid DESC LIMIT 5",
        (message.from_user.id,)
    )
    rows = cursor.fetchall()

    if not rows:
        await message.answer("История пуста")
        return

    text = "🧾 История:\n\n"
    for d, s in rows:
        text += f"{d} дней — {s}\n"

    await message.answer(text)


# ================== ADMIN ==================
@router.message(Command("admin"))
async def admin(message: Message):
    if message.from_user.id != ADMIN_ID:
        return

    cursor.execute("SELECT COUNT(*) FROM users")
    users = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM payments")
    pays = cursor.fetchone()[0]

    await message.answer(f"👑 Админ\n\nПользователи: {users}\nПлатежи: {pays}")


# ================== NAVIGATION ==================
@router.callback_query(F.data == "back")
async def back(call: CallbackQuery):
    await call.message.edit_text("Меню", reply_markup=menu())
    await call.answer()


@router.callback_query(F.data == "stars")
async def stars(call: CallbackQuery):
    await call.message.edit_text("⭐ Тарифы", reply_markup=plans("stars"))
    await call.answer()


@router.callback_query(F.data == "crypto")
async def crypto(call: CallbackQuery):
    await call.message.edit_text("💰 Тарифы", reply_markup=plans("crypto"))
    await call.answer()


@router.callback_query(F.data == "renew")
async def renew(call: CallbackQuery):
    await call.message.edit_text("🔁 Продлить:", reply_markup=plans("crypto"))
    await call.answer()


# ================== PLANS ==================
@router.callback_query(F.data.startswith("stars_"))
async def stars_plan(call: CallbackQuery):
    p = call.data.split("_")[1]
    await call.message.edit_text(
        f"{p} дней — {PLANS[p]['stars']}⭐",
        reply_markup=pay("stars", p)
    )
    await call.answer()


@router.callback_query(F.data.startswith("crypto_"))
async def crypto_plan(call: CallbackQuery):
    p = call.data.split("_")[1]
    await call.message.edit_text(
        f"{p} дней — {PLANS[p]['crypto']} USDT",
        reply_markup=pay("crypto", p)
    )
    await call.answer()


# ================== STARS ==================
@router.callback_query(F.data.startswith("pay_stars_"))
async def pay_stars(call: CallbackQuery):
    plan = call.data.split("_")[2]
    data = PLANS[plan]

    await bot.send_invoice(
        chat_id=call.message.chat.id,
        title="Access",
        description="Stars",
        payload=f"stars_{plan}",
        provider_token="",
        currency="XTR",
        prices=[LabeledPrice(label="Access", amount=data["stars"])]
    )

    await call.answer()


@router.pre_checkout_query()
async def pre_checkout(pre: PreCheckoutQuery):
    await pre.answer(ok=True)


@router.message(F.successful_payment)
async def stars_success(message: Message):
    plan = message.successful_payment.invoice_payload.split("_")[1]
    await grant_access(message.from_user.id, PLANS[plan]["days"])


# ================== CRYPTO ==================
@router.callback_query(F.data.startswith("pay_crypto_"))
async def pay_crypto(call: CallbackQuery):
    plan = call.data.split("_")[2]

    if call.from_user.id in active_invoices:
        await call.answer("⏳ Уже есть счёт", show_alert=True)
        return

    active_invoices[call.from_user.id] = plan
    data = PLANS[plan]

    r = requests.post(
        "https://pay.crypt.bot/api/createInvoice",
        headers={"Crypto-Pay-API-Token": CRYPTO_TOKEN},
        json={"asset": "USDT", "amount": data["crypto"]}
    ).json()

    invoice = r["result"]

    cursor.execute(
        "INSERT INTO payments VALUES (?, ?, ?, ?)",
        (invoice["invoice_id"], call.from_user.id, data["days"], "pending")
    )
    conn.commit()

    await call.message.answer(f"💰 Оплата:\n{invoice['pay_url']}")
    await call.answer()


# ================== RUN ==================
async def main():
    asyncio.create_task(remove_expired_users())
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
