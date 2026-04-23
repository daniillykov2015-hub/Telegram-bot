import asyncio
import logging
import os
import aiohttp
import aiosqlite

from datetime import datetime, timedelta

from aiogram import Bot, Dispatcher, Router, F
from aiogram.filters import CommandStart
from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    LabeledPrice,
    ChatJoinRequest,
)
from aiogram.fsm.storage.memory import MemoryStorage

# ================== CONFIG ==================
logging.basicConfig(level=logging.INFO)

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CRYPTO_TOKEN = os.getenv("CRYPTO_TOKEN")
CHANNEL_ID = os.getenv("TELEGRAM_GROUP_ID")

if not BOT_TOKEN:
    raise ValueError("TELEGRAM_BOT_TOKEN is missing")
if not CRYPTO_TOKEN:
    raise ValueError("CRYPTO_TOKEN is missing")
if not CHANNEL_ID:
    raise ValueError("TELEGRAM_GROUP_ID is missing")

CHANNEL_ID = int(CHANNEL_ID)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())
router = Router()
dp.include_router(router)

DB_NAME = "users.db"

# ================== DB ==================
async def init_db():
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            expiry TEXT,
            referrer INTEGER
        )
        """)

        await db.execute("""
        CREATE TABLE IF NOT EXISTS crypto_invoices (
            invoice_id TEXT PRIMARY KEY,
            user_id INTEGER,
            plan_id TEXT,
            status TEXT DEFAULT 'pending'
        )
        """)

        await db.commit()


# ================== HELPERS ==================
async def get_user(user_id):
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute(
            "SELECT * FROM users WHERE user_id=?",
            (user_id,)
        ) as cur:
            return await cur.fetchone()


async def extend_user(user_id, days):
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute(
            "SELECT expiry FROM users WHERE user_id=?",
            (user_id,)
        ) as cur:
            row = await cur.fetchone()

        if row and row[0]:
            current = datetime.fromisoformat(row[0])
            base = max(datetime.utcnow(), current)
        else:
            base = datetime.utcnow()

        new_expiry = base + timedelta(days=days)

        await db.execute("""
        INSERT INTO users (user_id, expiry, referrer)
        VALUES (?, ?, COALESCE((SELECT referrer FROM users WHERE user_id=?), NULL))
        ON CONFLICT(user_id) DO UPDATE SET expiry=excluded.expiry
        """, (user_id, new_expiry.isoformat(), user_id))

        await db.commit()


async def invoice_used(invoice_id: str):
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute(
            "SELECT status FROM crypto_invoices WHERE invoice_id=?",
            (invoice_id,)
        ) as cur:
            return await cur.fetchone()


async def mark_paid(invoice_id: str):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute(
            "UPDATE crypto_invoices SET status='paid' WHERE invoice_id=?",
            (invoice_id,)
        )
        await db.commit()


# ================== PLANS ==================
PLANS = {
    "1": {"stars": 550, "crypto": 5, "name": "1 день", "days": 1},
    "7": {"stars": 770, "crypto": 7, "name": "7 дней", "days": 7},
    "30": {"stars": 1100, "crypto": 10, "name": "30 дней", "days": 30},
}

MAIN_TEXT = "👋 Привет! Выбери способ оплаты 👇"

# ================== MENU ==================
def menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="⭐ Stars", callback_data="stars"),
            InlineKeyboardButton(text="💰 Crypto", callback_data="crypto"),
        ],
        [
            InlineKeyboardButton(text="👥 Реферал", callback_data="ref"),
        ],
        [
            InlineKeyboardButton(text="ℹ️ Информация", callback_data="info"),
            InlineKeyboardButton(text="💬 Поддержка", url="https://t.me/mistybibi"),
        ]
    ])


BACK_BTN = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="⬅ Назад", callback_data="back")]
])

# ================== START ==================
@router.message(CommandStart())
async def start(message: Message):
    args = message.text.split()

    if len(args) > 1 and args[1].isdigit():
        async with aiosqlite.connect(DB_NAME) as db:
            await db.execute("""
                INSERT OR IGNORE INTO users (user_id, referrer)
                VALUES (?, ?)
            """, (message.from_user.id, int(args[1])))
            await db.commit()

    await message.answer(MAIN_TEXT, reply_markup=menu())


# ================== REF ==================
@router.callback_query(F.data == "ref")
async def ref(call: CallbackQuery):
    bot_info = await bot.get_me()
    link = f"https://t.me/{bot_info.username}?start={call.from_user.id}"

    await call.message.edit_text(
        f"👥 Твоя ссылка:\n<code>{link}</code>",
        reply_markup=BACK_BTN,
        parse_mode="HTML"
    )


# ================== INFO ==================
@router.callback_query(F.data == "info")
async def info(call: CallbackQuery):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📄 Политика", callback_data="privacy")],
        [InlineKeyboardButton(text="⚖️ Условия", callback_data="terms")],
        [InlineKeyboardButton(text="⬅ Назад", callback_data="back")]
    ])

    await call.message.edit_text("ℹ️ Информация:", reply_markup=kb)


@router.callback_query(F.data == "privacy")
async def privacy(call: CallbackQuery):
    await call.message.edit_text(
        "📄 Политика конфиденциальности",
        reply_markup=BACK_BTN
    )


@router.callback_query(F.data == "terms")
async def terms(call: CallbackQuery):
    await call.message.edit_text(
        "⚖️ Условия использования",
        reply_markup=BACK_BTN
    )


# ================== BACK ==================
@router.callback_query(F.data == "back")
async def back(call: CallbackQuery):
    await call.message.edit_text(MAIN_TEXT, reply_markup=menu())


# ================== STARS ==================
@router.callback_query(F.data == "stars")
async def stars(call: CallbackQuery):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"{p['name']} — {p['stars']} ⭐",
                              callback_data=f"stars:{k}")]
        for k, p in PLANS.items()
    ] + [[InlineKeyboardButton(text="⬅ Назад", callback_data="back")]])

    await call.message.edit_text("⭐ Выбери тариф:", reply_markup=kb)


@router.callback_query(F.data.startswith("stars:"))
async def stars_pay(call: CallbackQuery):
    plan_id = call.data.split(":")[1]
    plan = PLANS[plan_id]

    link = await bot.create_invoice_link(
        title="Подписка",
        description=plan["name"],
        payload=f"stars_{plan_id}",
        provider_token="",
        currency="XTR",
        prices=[LabeledPrice(label="Stars", amount=plan["stars"])]
    )

    await call.message.edit_text(
        f"💰 {plan['stars']} ⭐",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Оплатить", url=link)],
            [InlineKeyboardButton(text="⬅ Назад", callback_data="stars")]
        ])
    )


# ================== CRYPTO ==================
@router.callback_query(F.data == "crypto")
async def crypto(call: CallbackQuery):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"{p['name']} — {p['crypto']}$",
                              callback_data=f"crypto:{k}")]
        for k, p in PLANS.items()
    ] + [[InlineKeyboardButton(text="⬅ Назад", callback_data="back")]])

    await call.message.edit_text("💰 Crypto:", reply_markup=kb)


@router.callback_query(F.data.startswith("crypto:"))
async def crypto_pay(call: CallbackQuery):
    plan_id = call.data.split(":")[1]
    plan = PLANS[plan_id]

    async with aiohttp.ClientSession() as session:
        async with session.post(
            "https://pay.crypt.bot/api/createInvoice",
            headers={"Crypto-Pay-API-Token": CRYPTO_TOKEN},
            json={
                "asset": "USDT",
                "amount": str(plan["crypto"]),
                "description": "Subscription"
            }
        ) as resp:
            data = await resp.json()

    if not data.get("ok"):
        await call.answer("Ошибка оплаты")
        return

    inv = data["result"]

    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("""
            INSERT OR IGNORE INTO crypto_invoices (invoice_id, user_id, plan_id)
            VALUES (?, ?, ?)
        """, (str(inv["invoice_id"]), call.from_user.id, plan_id))
        await db.commit()

    await call.message.edit_text(
        f"💰 {plan['crypto']} $",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Оплатить", url=inv["pay_url"])],
            [InlineKeyboardButton(text="⬅ Назад", callback_data="crypto")]
        ])
    )


# ================== PAYMENT ==================
@router.message(F.successful_payment)
async def paid(message: Message
