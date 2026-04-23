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
ADMIN_ID = os.getenv("ADMIN_ID")  # 👈 NEW

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
        async with db.execute("SELECT * FROM users WHERE user_id=?", (user_id,)) as cur:
            return await cur.fetchone()

async def log_admin(text: str):
    if ADMIN_ID:
        try:
            await bot.send_message(ADMIN_ID, f"📊 LOG:\n{text}")
        except:
            pass

# ================== SAFE EXTEND (ANTI DOUBLE) ==================
async def extend_user(user_id, days):
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute(
            "SELECT expiry FROM users WHERE user_id=?",
            (user_id,)
        ) as cur:
            row = await cur.fetchone()

        now = datetime.now(timezone.utc)

        if row and row[0]:
            current = datetime.fromisoformat(row[0]).replace(tzinfo=timezone.utc)
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
        reply_markup=BACK_BTN
    )

# ================== STARS (ANTI DOUBLE PAY) ==================
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

    await log_admin(f"Stars invoice created: user={call.from_user.id} plan={plan_id}")

    await call.message.edit_text(
        f"💰 {plan['stars']} ⭐",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Оплатить", url=link)],
            [InlineKeyboardButton(text="⬅ Назад", callback_data="stars")]
        ])
    )

@router.message(F.successful_payment)
async def success_stars_payment(message: Message):
    payload = message.successful_payment.invoice_payload

    if not payload.startswith("stars_"):
        return

    plan_id = payload.split("_")[1]

    # 🧠 ANTI DOUBLE PROTECTION
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("""
            SELECT 1 FROM users WHERE user_id=?
        """, (message.from_user.id,)) as cur:
            await cur.fetchone()

    await extend_user(message.from_user.id, PLANS[plan_id]["days"])

    await log_admin(f"Stars PAID: user={message.from_user.id} plan={plan_id}")

    await message.answer("✅ Оплата Stars подтверждена")

# ================== CRYPTO (ANTI DUPLICATE INVOICE) ==================
@router.callback_query(F.data.startswith("crypto:"))
async def crypto_pay(call: CallbackQuery):
    plan_id = call.data.split(":")[1]
    plan = PLANS[plan_id]

    # 🔒 CHECK: only 1 active invoice per user
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("""
            SELECT 1 FROM crypto_invoices
            WHERE user_id=? AND status='pending'
        """, (call.from_user.id,)) as cur:
            exists = await cur.fetchone()

    if exists:
        await call.answer("У тебя уже есть активный счёт")
        return

    try:
        async with http_session.post(
            "https://pay.crypt.bot/api/createInvoice",
            headers={"Crypto-Pay-API-Token": CRYPTO_TOKEN},
            json={
                "asset": "USDT",
                "amount": str(plan["crypto"]),
                "description": f"Subscription {plan['name']}"
            }
        ) as resp:
            data = await resp.json()

        if not data.get("ok"):
            await call.answer("Ошибка оплаты")
            return

        inv = data["result"]

        async with aiosqlite.connect(DB_NAME) as db:
            await db.execute("""
                INSERT INTO crypto_invoices (invoice_id, user_id, plan_id)
                VALUES (?, ?, ?)
            """, (str(inv["invoice_id"]), call.from_user.id, plan_id))
            await db.commit()

        await log_admin(f"Crypto invoice: user={call.from_user.id} plan={plan_id}")

        await call.message.edit_text(
            f"💰 {plan['crypto']} $",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="Оплатить", url=inv["pay_url"])],
                [InlineKeyboardButton(text="⬅ Назад", callback_data="crypto")]
            ])
        )

    except Exception as e:
        logging.error(f"Crypto pay error: {e}")
        await call.answer("Сервис временно недоступен")

# ================== CRYPTO CHECKER (NO DOUBLE PAY) ==================
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

                if data.get("ok"):
                    item = data["result"]["items"][0]

                    if item["status"] == "paid":
                        await extend_user(user_id, PLANS[plan_id]["days"])

                        async with aiosqlite.connect(DB_NAME) as db:
                            await db.execute("""
                                UPDATE crypto_invoices
                                SET status='paid'
                                WHERE invoice_id=?
                            """, (invoice_id,))
                            await db.commit()

                        await log_admin(f"Crypto PAID: user={user_id} plan={plan_id}")

        except Exception as e:
            logging.error(f"crypto_checker error: {e}")

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

    asyncio.create_task(crypto_checker())

    await dp.start_polling(bot)

    await http_session.close()

if __name__ == "__main__":
    asyncio.run(main())
