import asyncio
import logging
import os
import aiohttp
import aiosqlite

from datetime import datetime, timedelta, timezone

from aiogram import Bot, Dispatcher, Router, F
from aiogram.filters import CommandStart
from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    LabeledPrice,
    ChatJoinRequest,
    PreCheckoutQuery,
    SuccessfulPayment,
)
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.client.default import DefaultBotProperties

# ================== CONFIG ==================
logging.basicConfig(level=logging.INFO)

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CRYPTO_TOKEN = os.getenv("CRYPTO_TOKEN")
CHANNEL_ID = os.getenv("TELEGRAM_GROUP_ID")
ADMIN_ID = os.getenv("ADMIN_ID")

if not BOT_TOKEN:
    raise ValueError("TELEGRAM_BOT_TOKEN is missing")
if not CRYPTO_TOKEN:
    raise ValueError("CRYPTO_TOKEN is missing")
if not CHANNEL_ID:
    raise ValueError("TELEGRAM_GROUP_ID is missing")

CHANNEL_ID = int(CHANNEL_ID)
ADMIN_ID = int(ADMIN_ID) if ADMIN_ID else None

bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
dp = Dispatcher(storage=MemoryStorage())
router = Router()
dp.include_router(router)

DB_NAME = "users.db"

http_session = None

# ================== PRO 4.0: DB INIT ==================
async def init_analytics():
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("""
        CREATE TABLE IF NOT EXISTS payments_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            amount REAL,
            currency TEXT,
            method TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        """)
        await db.commit()

# ================== PRO 4.0: ANTI FLOOD ==================
class AntiFloodMiddleware:
    def __init__(self):
        self.last = {}

    async def __call__(self, handler, event, data):
        user = getattr(event, "from_user", None)
        if user:
            now = asyncio.get_event_loop().time()
            if now - self.last.get(user.id, 0) < 0.7:
                return
            self.last[user.id] = now
        return await handler(event, data)

# ================== PRO 4.0: LOGGING ==================
async def log_payment(user_id, amount, currency, method):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("""
        INSERT INTO payments_log (user_id, amount, currency, method)
        VALUES (?, ?, ?, ?)
        """, (user_id, amount, currency, method))
        await db.commit()

# ================== ORIGINAL DB ==================
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
        async with db.execute("SELECT * FROM users WHERE user_id=?", (user_id,)) as cur:
            return await cur.fetchone()

async def extend_user(user_id, days):
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("SELECT expiry FROM users WHERE user_id=?", (user_id,)) as cur:
            row = await cur.fetchone()

        now = datetime.now(timezone.utc)

        if row and row[0]:
            current = datetime.fromisoformat(row[0])
            if current.tzinfo is None:
                current = current.replace(tzinfo=timezone.utc)
            base = max(now, current)
        else:
            base = now

        new_expiry = base + timedelta(days=days)

        await db.execute("""
        INSERT INTO users (user_id, expiry, referrer)
        VALUES (?, ?, COALESCE((SELECT referrer FROM users WHERE user_id=?), NULL))
        ON CONFLICT(user_id) DO UPDATE SET expiry=excluded.expiry
        """, (user_id, new_expiry.isoformat(), user_id))

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
            await db.execute("INSERT OR IGNORE INTO users (user_id, referrer) VALUES (?, ?)",
                             (message.from_user.id, int(args[1])))
            await db.commit()

    await message.answer(MAIN_TEXT, reply_markup=menu())

# ================== REF / INFO / BACK (UNCHANGED) ==================
@router.callback_query(F.data == "ref")
async def ref(call: CallbackQuery):
    bot_info = await bot.get_me()
    link = f"https://t.me/{bot_info.username}?start={call.from_user.id}"
    await call.message.edit_text(f"👥 Твоя ссылка:\n<code>{link}</code>", reply_markup=BACK_BTN)

@router.callback_query(F.data == "info")
async def info(call: CallbackQuery):
    await call.message.edit_text(
        "ℹ️ Информация:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📄 Политика", callback_data="privacy")],
            [InlineKeyboardButton(text="⚖️ Условия", callback_data="terms")],
            [InlineKeyboardButton(text="⬅ Назад", callback_data="back")]
        ])
    )

@router.callback_query(F.data == "privacy")
async def privacy(call: CallbackQuery):
    await call.message.edit_text("📄 Политика", reply_markup=BACK_BTN)

@router.callback_query(F.data == "terms")
async def terms(call: CallbackQuery):
    await call.message.edit_text("⚖️ Условия", reply_markup=BACK_BTN)

@router.callback_query(F.data == "back")
async def back(call: CallbackQuery):
    await call.message.edit_text(MAIN_TEXT, reply_markup=menu())

# ================== PRO 4.0 PAYMENT LOG HOOK ==================
async def safe_log(user_id, amount, currency, method):
    try:
        await log_payment(user_id, amount, currency, method)
    except:
        pass

# ================== STARS ==================
@router.message(F.successful_payment)
async def success_stars_payment(message: Message):
    payload = message.successful_payment.invoice_payload

    if payload.startswith("stars_"):
        plan_id = payload.split("_")[1]

        await extend_user(message.from_user.id, PLANS[plan_id]["days"])

        await safe_log(
            message.from_user.id,
            message.successful_payment.total_amount / 100,
            "XTR",
            "stars"
        )

        await message.answer("✅ Оплата Stars подтверждена")

# ================== CRYPTO ==================
@router.callback_query(F.data.startswith("crypto:"))
async def crypto_pay(call: CallbackQuery):
    plan_id = call.data.split(":")[1]
    plan = PLANS[plan_id]

    try:
        global http_session

        async with http_session.post(
            "https://pay.crypt.bot/api/createInvoice",
            headers={"Crypto-Pay-API-Token": CRYPTO_TOKEN},
            json={
                "asset": "USDT",
                "amount": str(plan["crypto"]),
                "description": plan["name"]
            }
        ) as resp:
            data = await resp.json()

        if not data.get("ok"):
            return await call.answer("Ошибка оплаты")

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

    except Exception as e:
        logging.error(e)

# ================== CRYPTO CHECKER (SAFE + LOG) ==================
async def crypto_checker():
    while True:
        try:
            async with aiosqlite.connect(DB_NAME) as db:
                async with db.execute("""
                SELECT invoice_id, user_id, plan_id
                FROM crypto_invoices
                WHERE status='pending'
                """) as cur:
                    invoices = await cur.fetchall()

            for invoice_id, user_id, plan_id in invoices:

                async with http_session.get(
                    f"https://pay.crypt.bot/api/getInvoices?invoice_ids={invoice_id}",
                    headers={"Crypto-Pay-API-Token": CRYPTO_TOKEN}
                ) as resp:
                    data = await resp.json()

                items = data.get("result", {}).get("items", [])
                if not items:
                    continue

                item = items[0]

                if item["status"] == "paid":

                    await extend_user(user_id, PLANS[plan_id]["days"])

                    await safe_log(
                        user_id,
                        PLANS[plan_id]["crypto"],
                        "USDT",
                        "crypto"
                    )

                    async with aiosqlite.connect(DB_NAME) as db:
                        await db.execute("""
                        UPDATE crypto_invoices
                        SET status='paid'
                        WHERE invoice_id=? AND status='pending'
                        """, (invoice_id,))
                        await db.commit()

        except Exception as e:
            logging.error(e)

        await asyncio.sleep(20)

# ================== JOIN ==================
@router.chat_join_request()
async def join(req: ChatJoinRequest):
    user = await get_user(req.from_user.id)

    if user and user[1]:
        if datetime.fromisoformat(user[1]).replace(tzinfo=timezone.utc) > datetime.now(timezone.utc):
            await req.approve()
            return

    await req.decline()

# ================== MAIN ==================
async def main():
    global http_session
    http_session = aiohttp.ClientSession()

    await init_db()
    await init_analytics()

    dp.message.middleware(AntiFloodMiddleware())
    dp.callback_query.middleware(AntiFloodMiddleware())

    asyncio.create_task(crypto_checker())

    await dp.start_polling(bot)

    await http_session.close()

if __name__ == "__main__":
    asyncio.run(main())
