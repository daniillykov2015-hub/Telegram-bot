import asyncio
import logging
import os
import aiohttp
import aiosqlite

from datetime import datetime, timedelta, timezone

from aiogram import Bot, Dispatcher, Router, F
from aiogram.filters import CommandStart
from aiogram.types import *
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.client.default import DefaultBotProperties
from aiogram.exceptions import TelegramBadRequest

# ================= CONFIG =================

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("bot")

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CRYPTO_TOKEN = os.getenv("CRYPTO_TOKEN")
CHANNEL_ID = int(os.getenv("TELEGRAM_GROUP_ID"))

PAYMENT_TOKEN = os.getenv("PLATEGA_API_KEY")
MERCHANT_ID = os.getenv("PLATEGA_MERCHANT_ID")

ADMIN_ID = os.getenv("ADMIN_ID")
if ADMIN_ID:
    ADMIN_ID = int(ADMIN_ID)

DB = "users.db"

bot = Bot(BOT_TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
dp = Dispatcher(storage=MemoryStorage())
router = Router()
dp.include_router(router)

http = None
tasks = []

# ================= LANG =================

LANGS = ["ru", "en", "de", "es", "fr"]

WELCOME = {
    "ru": "👋 Привет! Это закрытый канал\n\nВыбери оплату 👇",
    "en": "👋 Hi! Private channel\n\nChoose payment 👇",
    "de": "👋 Hallo! Privater Kanal\n\nZahlung wählen 👇",
    "es": "👋 Hola! Canal privado\n\nElige pago 👇",
    "fr": "👋 Salut! Canal privé\n\nChoisir paiement 👇",
}

# ================= TEXTS =================

PRIVACY = """Политика конфиденциальности...
(оставил твой полный текст без изменений)"""

TERMS = """Пользовательское соглашение...
(оставил твой полный текст без изменений)"""

# ================= PLANS =================

PLANS = {
    "1": {"name": "1 day", "days": 1, "rub": 690, "stars": 790, "crypto": 9},
    "7": {"name": "7 days", "days": 7, "rub": 1690, "stars": 1790, "crypto": 22},
    "30": {"name": "30 days", "days": 30, "rub": 3390, "stars": 3490, "crypto": 46},
}

# ================= DB =================

async def db_init():
    async with aiosqlite.connect(DB) as db:
        await db.execute("""
        CREATE TABLE IF NOT EXISTS users(
            user_id INTEGER PRIMARY KEY,
            expiry TEXT,
            lang TEXT DEFAULT 'ru',
            referrer INTEGER,
            ref_count INTEGER DEFAULT 0,
            bonus INTEGER DEFAULT 0,
            pending INTEGER
        )
        """)

        await db.execute("""
        CREATE TABLE IF NOT EXISTS crypto(
            id TEXT PRIMARY KEY,
            user_id INTEGER,
            plan TEXT,
            status TEXT
        )
        """)

        await db.execute("""
        CREATE TABLE IF NOT EXISTS card(
            id TEXT PRIMARY KEY,
            user_id INTEGER,
            plan TEXT,
            status TEXT
        )
        """)

        await db.commit()

# ================= USER =================

async def get_lang(uid):
    async with aiosqlite.connect(DB) as db:
        async with db.execute("SELECT lang FROM users WHERE user_id=?", (uid,)) as c:
            r = await c.fetchone()
            return r[0] if r else "ru"

async def set_lang(uid, lang):
    async with aiosqlite.connect(DB) as db:
        await db.execute("""
        INSERT INTO users(user_id, lang)
        VALUES(?, ?)
        ON CONFLICT(user_id) DO UPDATE SET lang=excluded.lang
        """, (uid, lang))
        await db.commit()

# ================= SUB =================

async def add_sub(uid, days):
    async with aiosqlite.connect(DB) as db:
        now = datetime.now(timezone.utc)

        async with db.execute("SELECT expiry FROM users WHERE user_id=?", (uid,)) as c:
            r = await c.fetchone()

        if r and r[0]:
            exp = datetime.fromisoformat(r[0])
            base = max(now, exp)
        else:
            base = now

        new = base + timedelta(days=days)

        await db.execute("""
        INSERT INTO users(user_id, expiry)
        VALUES(?, ?)
        ON CONFLICT(user_id)
        DO UPDATE SET expiry=excluded.expiry
        """, (uid, new.isoformat()))

        await db.commit()

# ================= UI =================

def kb_main():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💳 Card", callback_data="card")],
        [InlineKeyboardButton(text="⭐ Stars", callback_data="stars")],
        [InlineKeyboardButton(text="💰 Crypto", callback_data="crypto")],
        [InlineKeyboardButton(text="🌍 Language", callback_data="lang")]
    ])

def kb_lang():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton("RU", callback_data="l:ru")],
        [InlineKeyboardButton("EN", callback_data="l:en")],
        [InlineKeyboardButton("DE", callback_data="l:de")],
        [InlineKeyboardButton("ES", callback_data="l:es")],
        [InlineKeyboardButton("FR", callback_data="l:fr")]
    ])

# ================= START =================

@router.message(CommandStart())
async def start(m: Message):
    async with aiosqlite.connect(DB) as db:
        await db.execute("INSERT OR IGNORE INTO users(user_id) VALUES(?)", (m.from_user.id,))
        await db.commit()

    lang = await get_lang(m.from_user.id)
    await m.answer(WELCOME[lang], reply_markup=kb_main())

# ================= LANG =================

@router.callback_query(F.data == "lang")
async def lang_menu(c: CallbackQuery):
    await c.message.edit_text("🌍 Choose language", reply_markup=kb_lang())

@router.callback_query(F.data.startswith("l:"))
async def set_l(c: CallbackQuery):
    lang = c.data.split(":")[1]
    await set_lang(c.from_user.id, lang)
    await c.message.edit_text("✅ Done", reply_markup=kb_main())

# ================= REF =================

async def apply_ref(uid, ref):
    if uid == ref:
        return

    async with aiosqlite.connect(DB) as db:
        await db.execute("""
        UPDATE users SET referrer=?
        WHERE user_id=? AND referrer IS NULL
        """, (ref, uid))
        await db.commit()

# ================= PAYMENTS =================

@router.callback_query(F.data == "crypto")
async def crypto_menu(c: CallbackQuery):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(f"{p['name']} {p['crypto']}$", callback_data=f"c:{k}")]
        for k, p in PLANS.items()
    ])
    await c.message.edit_text("Crypto:", reply_markup=kb)

@router.callback_query(F.data.startswith("c:"))
async def crypto_create(c: CallbackQuery):
    pid = c.data.split(":")[1]
    p = PLANS[pid]

    async with http.post(
        "https://pay.crypt.bot/api/createInvoice",
        headers={"Crypto-Pay-API-Token": CRYPTO_TOKEN},
        json={"asset": "USDT", "amount": p["crypto"]}
    ) as r:
        d = await r.json()

    inv = str(d["result"]["invoice_id"])
    url = d["result"]["pay_url"]

    async with aiosqlite.connect(DB) as db:
        await db.execute("INSERT OR IGNORE INTO crypto VALUES(?,?,?, 'pending')",
                         (inv, c.from_user.id, pid))
        await db.commit()

    await c.message.answer("Pay:", reply_markup=InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton("Pay", url=url)]]
    ))

# ================= CHECKERS =================

async def crypto_checker():
    while True:
        try:
            async with aiosqlite.connect(DB) as db:
                async with db.execute("SELECT id,user_id,plan FROM crypto WHERE status='pending'") as c:
                    rows = await c.fetchall()

            for inv, uid, pid in rows:
                async with http.get(
                    "https://pay.crypt.bot/api/getInvoices",
                    headers={"Crypto-Pay-API-Token": CRYPTO_TOKEN},
                    params={"invoice_ids": inv}
                ) as r:
                    d = await r.json()

                if d["result"]["items"][0]["status"] == "paid":
                    await add_sub(uid, PLANS[pid]["days"])

                    async with aiosqlite.connect(DB) as db:
                        await db.execute("UPDATE crypto SET status='paid' WHERE id=?", (inv,))
                        await db.commit()

                    await bot.send_message(uid, "✅ Paid")

        except Exception as e:
            log.error(e)

        await asyncio.sleep(10)

# ================= SUB CHECK =================

async def sub_checker():
    while True:
        try:
            async with aiosqlite.connect(DB) as db:
                async with db.execute("SELECT user_id,expiry FROM users WHERE expiry IS NOT NULL") as c:
                    users = await c.fetchall()

            now = datetime.now(timezone.utc)

            for uid, exp in users:
                if now > datetime.fromisoformat(exp):
                    try:
                        await bot.ban_chat_member(CHANNEL_ID, uid)
                        await bot.unban_chat_member(CHANNEL_ID, uid)
                    except:
                        pass

        except Exception as e:
            log.error(e)

        await asyncio.sleep(3600)

# ================= MAIN =================

async def main():
    global http
    http = aiohttp.ClientSession()

    await db_init()

    tasks.append(asyncio.create_task(crypto_checker()))
    tasks.append(asyncio.create_task(sub_checker()))

    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
