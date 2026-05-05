import asyncio
import logging
import os
import aiohttp
import aiosqlite

from datetime import datetime, timedelta, timezone

from aiogram import Bot, Dispatcher, Router, F
from aiogram.filters import CommandStart
from aiogram.types import (
    Message, CallbackQuery,
    InlineKeyboardMarkup, InlineKeyboardButton,
    LabeledPrice, PreCheckoutQuery,
    ChatMemberUpdated
)
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.client.default import DefaultBotProperties
from aiogram.exceptions import TelegramBadRequest

# ================== CONFIG ==================
logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CRYPTO_TOKEN = os.getenv("CRYPTO_TOKEN")
CHANNEL_ID = int(os.getenv("TELEGRAM_GROUP_ID"))
PAYMENT_TOKEN = os.getenv("PLATEGA_API_KEY")
MERCHANT_ID = os.getenv("PLATEGA_MERCHANT_ID")
ADMIN_ID = int(os.getenv("ADMIN_ID")) if os.getenv("ADMIN_ID") else None

DB = "users.db"

bot = Bot(BOT_TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
dp = Dispatcher(storage=MemoryStorage())
router = Router()
dp.include_router(router)

http = None
tasks = []

# ================== LANG ==================
LANGS = ["ru", "en", "es", "de", "fr"]

TEXTS = {
"ru": {
"start": "👋 Привет! Закрытый канал",
"choose": "Выбери оплату:",
"back": "⬅ Назад"
},
"en": {
"start": "👋 Welcome to private channel",
"choose": "Choose payment:",
"back": "⬅ Back"
},
"es": {
"start": "👋 Canal privado",
"choose": "Elige pago:",
"back": "⬅ Volver"
},
"de": {
"start": "👋 Privater Kanal",
"choose": "Zahlung wählen:",
"back": "⬅ Zurück"
},
"fr": {
"start": "👋 Canal privé",
"choose": "Choisissez paiement:",
"back": "⬅ Retour"
}
}

# ================== PLANS ==================
PLANS = {
"1": {"name": "1 day", "days": 1, "rub": 690, "stars": 790, "crypto": 9},
"7": {"name": "7 days", "days": 7, "rub": 1690, "stars": 1790, "crypto": 22},
"30": {"name": "30 days", "days": 30, "rub": 3390, "stars": 3490, "crypto": 46},
}

# ================== DB ==================
async def db_init():
    async with aiosqlite.connect(DB) as db:
        await db.executescript("""
        CREATE TABLE IF NOT EXISTS users(
            user_id INTEGER PRIMARY KEY,
            expiry TEXT,
            ref INTEGER,
            lang TEXT DEFAULT 'ru',
            pending_days INTEGER
        );
        CREATE TABLE IF NOT EXISTS card(
            id TEXT PRIMARY KEY,
            user_id INTEGER,
            plan TEXT,
            status TEXT
        );
        CREATE TABLE IF NOT EXISTS crypto(
            id TEXT PRIMARY KEY,
            user_id INTEGER,
            plan TEXT,
            status TEXT
        );
        """)
        await db.commit()

# ================== HELPERS ==================
async def get_lang(uid):
    async with aiosqlite.connect(DB) as db:
        async with db.execute("SELECT lang FROM users WHERE user_id=?", (uid,)) as c:
            r = await c.fetchone()
            return r[0] if r else "ru"

async def set_lang(uid, lang):
    async with aiosqlite.connect(DB) as db:
        await db.execute("INSERT OR IGNORE INTO users(user_id) VALUES(?)", (uid,))
        await db.execute("UPDATE users SET lang=? WHERE user_id=?", (lang, uid))
        await db.commit()

async def extend(uid, days):
    async with aiosqlite.connect(DB) as db:
        cur = await db.execute("SELECT expiry FROM users WHERE user_id=?", (uid,))
        row = await cur.fetchone()

        now = datetime.now(timezone.utc)
        base = now

        if row and row[0]:
            old = datetime.fromisoformat(row[0])
            base = max(now, old)

        new = base + timedelta(days=days)

        await db.execute("""
        INSERT INTO users(user_id, expiry)
        VALUES(?,?)
        ON CONFLICT(user_id) DO UPDATE SET expiry=excluded.expiry
        """, (uid, new.isoformat()))
        await db.commit()

# ================== KEYBOARDS ==================
def lang_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=l.upper(), callback_data=f"lang:{l}")]
        for l in LANGS
    ])

def main_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💳 Card", callback_data="card")],
        [InlineKeyboardButton(text="⭐ Stars", callback_data="stars")],
        [InlineKeyboardButton(text="💰 Crypto", callback_data="crypto")],
        [InlineKeyboardButton(text="🌍 Lang", callback_data="lang_menu")]
    ])

# ================== START ==================
@router.message(CommandStart())
async def start(m: Message):
    uid = m.from_user.id

    async with aiosqlite.connect(DB) as db:
        await db.execute("INSERT OR IGNORE INTO users(user_id) VALUES(?)", (uid,))
        await db.commit()

    lang = await get_lang(uid)
    await m.answer(TEXTS[lang]["start"], reply_markup=main_kb())

# ================== LANG ==================
@router.callback_query(F.data == "lang_menu")
async def lang_menu(c: CallbackQuery):
    await c.message.edit_text("🌍 Language:", reply_markup=lang_kb())
    await c.answer()

@router.callback_query(F.data.startswith("lang:"))
async def lang_set(c: CallbackQuery):
    lang = c.data.split(":")[1]
    await set_lang(c.from_user.id, lang)
    await c.message.edit_text("✅ OK", reply_markup=main_kb())

# ================== PAY MENU ==================
@router.callback_query(F.data == "card")
@router.callback_query(F.data == "stars")
@router.callback_query(F.data == "crypto")
async def pay_menu(c: CallbackQuery):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"{p['name']} {p['rub']}₽", callback_data=f"pay:{k}")]
        for k, p in PLANS.items()
    ] + [[InlineKeyboardButton(text="⬅", callback_data="back")]])

    await c.message.edit_text("Choose plan:", reply_markup=kb)

@router.callback_query(F.data == "back")
async def back(c: CallbackQuery):
    await c.message.edit_text("Menu", reply_markup=main_kb())

# ================== PAYMENT (SIMPLIFIED HOOKS) ==================
@router.callback_query(F.data.startswith("pay:"))
async def pay(c: CallbackQuery):
    plan = PLANS[c.data.split(":")[1]]
    uid = c.from_user.id

    await extend(uid, plan["days"])

    await c.message.answer(f"✅ Paid {plan['name']} activated")

# ================== JOIN CHECK ==================
@router.chat_member()
async def join(event: ChatMemberUpdated):
    if event.new_chat_member.status == "member":
        uid = event.from_user.id

        async with aiosqlite.connect(DB) as db:
            cur = await db.execute("SELECT pending_days FROM users WHERE user_id=?", (uid,))
            row = await cur.fetchone()

        if row and row[0]:
            await extend(uid, row[0])

# ================== SUB CHECK ==================
async def checker():
    while True:
        async with aiosqlite.connect(DB) as db:
            cur = await db.execute("SELECT user_id, expiry FROM users WHERE expiry IS NOT NULL")
            rows = await cur.fetchall()

        now = datetime.now(timezone.utc)

        for uid, exp in rows:
            if exp and datetime.fromisoformat(exp) < now:
                try:
                    await bot.ban_chat_member(CHANNEL_ID, uid)
                    await bot.unban_chat_member(CHANNEL_ID, uid)
                except:
                    pass

        await asyncio.sleep(3600)

# ================== MAIN ==================
async def main():
    global http
    http = aiohttp.ClientSession()

    await db_init()

    asyncio.create_task(checker())

    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
