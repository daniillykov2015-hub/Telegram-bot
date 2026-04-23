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
    PreCheckoutQuery,
    ChatJoinRequest,
)

# ================== CONFIG ==================
logging.basicConfig(level=logging.INFO)

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CRYPTO_TOKEN = os.getenv("CRYPTO_TOKEN")
CHANNEL_ID = int(os.getenv("TELEGRAM_GROUP_ID"))

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
router = Router()
dp.include_router(router)

DB_NAME = "users.db"

# ================== DATABASE ==================
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
                plan_id TEXT
            )
        """)
        await db.commit()

async def get_user(user_id):
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("SELECT * FROM users WHERE user_id=?", (user_id,)) as cursor:
            return await cursor.fetchone()

async def extend_user(user_id, days):
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("SELECT expiry FROM users WHERE user_id=?", (user_id,)) as cursor:
            row = await cursor.fetchone()
            if row and row[0]:
                current_expiry = datetime.fromisoformat(row[0])
                expiry = max(datetime.utcnow(), current_expiry) + timedelta(days=days)
            else:
                expiry = datetime.utcnow() + timedelta(days=days)
            
            await db.execute(
                "INSERT OR REPLACE INTO users (user_id, expiry, referrer) "
                "VALUES (?, ?, COALESCE((SELECT referrer FROM users WHERE user_id=?), NULL))",
                (user_id, expiry.isoformat(), user_id)
            )
            await db.commit()

# ================== PLANS & TEXTS ==================
PLANS = {
    "1": {"stars": 550, "crypto": 5, "name": "1 день", "days": 1},
    "7": {"stars": 770, "crypto": 7, "name": "7 дней", "days": 7},
    "30": {"stars": 1100, "crypto": 10, "name": "30 дней", "days": 30},
}

MAIN_TEXT = (
    "👋 Привет, я Ева и это мой закрытый канал\n\n"
    "❓ Что внутри?\n\n"
    "Закрытый контент по подписке\n"
    "💎 Без ограничений\n"
    "🔥 Обновления регулярно\n\n"
    "Выбери способ оплаты 👇"
)

PRIVACY_TEXT = "📄 <b>Политика конфиденциальности</b>\n\nЗдесь должен быть твой текст политики..."
TERMS_TEXT = "⚖️ <b>Пользовательское соглашение</b>\n\nЗдесь должен быть твой текст соглашения..."

# ================== MENU ==================
def menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="⭐ Stars", callback_data="stars"),
            InlineKeyboardButton(text="💰 Crypto", callback_data="crypto"),
        ],
        [
            InlineKeyboardButton(text="👥 Реферальная система", callback_data="ref"),
            InlineKeyboardButton(text="💬 Поддержка", url="https://t.me/mistybibi"),
        ],
        [InlineKeyboardButton(text="ℹ️ Информация", callback_data="info")]
    ])

# ================== HANDLERS ==================

@router.message(CommandStart())
async def start(message: Message):
    args = message.text.split()
    if len(args) > 1 and args[1].isdigit():
        async with aiosqlite.connect(DB_NAME) as db:
            await db.execute("INSERT OR IGNORE INTO users (user_id, referrer) VALUES (?, ?)", 
                           (message.from_user.id, int(args[1])))
            await db.commit()
    await message.answer(MAIN_TEXT, reply_markup=menu())

@router.callback_query(F.data == "back")
async def back(call: CallbackQuery):
    await call.message.edit_text(MAIN_TEXT, reply_markup=menu())
    await call.answer()

# --- БЛОК ИНФОРМАЦИЯ (со всеми пунктами) ---
@router.callback_query(F.data == "info")
async def info_menu(call: CallbackQuery):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📄 Политика конфиденциальности", callback_data="privacy")],
        [InlineKeyboardButton(text="⚖️ Пользовательское соглашение", callback_data="terms")],
        [InlineKeyboardButton(text="⬅ Назад", callback_data="back")]
    ])
    await call.message.edit_text("ℹ️ <b>Раздел информации:</b>", reply_markup=kb, parse_mode="HTML")
    await call.answer()

@router.callback_query(F.data == "privacy")
async def show_privacy(call: CallbackQuery):
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⬅ Назад", callback_data="info")]])
    await call.message.edit_text(PRIVACY_TEXT, reply_markup=kb, parse_mode="HTML")

@router.callback_query(F.data == "terms")
async def show_terms(call: CallbackQuery):
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⬅ Назад", callback_data="info")]])
    await call.message.edit_text(TERMS_TEXT, reply_markup=kb, parse_mode="HTML")

# --- РЕФЕРАЛКА ---
@router.callback_query(F.data == "ref")
async def ref_system(call: CallbackQuery):
    bot_info = await bot.get_me()
    ref_link = f"https://t.me/{bot_info.username}?start={call.from_user.id}"
    text = (
        "<b>👥 Реферальная система</b>\n\n"
        f"Твоя ссылка для приглашения друзей:\n<code>{ref_link}</code>\n\n"
        "Приглашай людей и получай доступ бесплатно!"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⬅ Назад", callback_data="back")]])
    await call.message.edit_text(text, reply_markup=kb, parse_mode="HTML")

# --- ОПЛАТА (STARS) ---
@router.callback_query(F.data == "stars")
async def stars_menu(call: CallbackQuery):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="1 день — 550 ⭐", callback_data="stars_confirm:1")],
        [InlineKeyboardButton(text="7 дней — 770 ⭐", callback_data="stars_confirm:7")],
        [InlineKeyboardButton(text="30 дней — 1100 ⭐", callback_data="stars_confirm:30")],
        [InlineKeyboardButton(text="⬅ Назад", callback_data="back")]
    ])
    await call.message.edit_text("⭐ Выберите тариф Stars:", reply_markup=kb)

@router.callback_query(F.data.startswith("stars_confirm:"))
async def stars_confirm(call: CallbackQuery):
    plan_id = call.data.split(":")[1]
    plan = PLANS[plan_id]
    invoice_link = await bot.create_invoice_link(
        title="Подписка", description=f"Доступ на {plan['name']}", payload=f"stars_{plan_id}",
        provider_token="", currency="XTR", prices=[LabeledPrice(label="Stars", amount=plan['stars'])]
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💸 Оплатить", url=invoice_link)],
        [InlineKeyboardButton(text="⬅ Назад", callback_data="stars")]
    ])
    await call.message.edit_text(f"💰 К оплате: {plan['stars']} ⭐\nНажми кнопку ниже:", reply_markup=kb)

# --- ОПЛАТА (CRYPTO) ---
@router.callback_query(F.data == "crypto")
async def crypto_menu(call: CallbackQuery):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="1 день — 5$", callback_data="crypto_confirm:1")],
        [InlineKeyboardButton(text="7 дней — 7$", callback_data="crypto_confirm:7")],
        [InlineKeyboardButton(text="30 дней — 10$", callback_data="crypto_confirm:30")],
        [InlineKeyboardButton(text="⬅ Назад", callback_data="back")]
    ])
    await call.message.edit_text("💰 Выберите тариф Crypto:", reply_markup=kb)

@router.callback_query(F.data.startswith("crypto_confirm:"))
async def crypto_confirm(call: CallbackQuery):
    plan_id = call.data.split(":")[1]
    plan = PLANS[plan_id]
    async with aiohttp.ClientSession() as session:
        async with session.post("https://pay.crypt.bot/api/createInvoice",
            headers={"Crypto-Pay-API-Token": CRYPTO_TOKEN},
            json={"asset": "USDT", "amount": str(plan["crypto"]), "description": "Sub"}) as resp:
            r = await resp.json()
    if r.get("ok"):
        inv_id, pay_url = r["result"]["invoice_id"], r["result"]["pay_url"]
        async with aiosqlite.connect(DB_NAME) as db:
            await db.execute("INSERT INTO crypto_invoices VALUES (?, ?, ?)", (str(inv_id), call.from_user.id, plan_id))
            await db.commit()
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="💸 Оплатить", url=pay_url)],
            [InlineKeyboardButton(text="⬅ Назад", callback_data="crypto")]
        ])
        await call.message.edit_text(f"💰 К оплате: {plan['crypto']} $\nНажми кнопку ниже:", reply_markup=kb)

# --- ПРОВЕРКА И ПРИЕМ В КАНАЛ ---
@router.pre_checkout_query()
async def pre_checkout(pre: PreCheckoutQuery):
    await pre.answer(ok=True)

@router.message(F.successful_payment)
async def success_stars(message: Message):
    plan_id = message.successful_payment.invoice_payload.split("_")[1]
    await extend_user(message.from_user.id, PLANS[plan_id]["days"])
    await message.answer("✅ Готово! Теперь просто подай заявку в канал.")

@router.chat_join_request()
async def approve_request(request: ChatJoinRequest):
    user = await get_user(request.from_user.id)
    if user and user[1] and datetime.fromisoformat(user[1]) > datetime.utcnow():
        await request.approve()
    else:
        await bot.send_message(request.from_user.id, "❌ Сначала оплатите подписку в боте.")

async def check_crypto():
    while True:
        await asyncio.sleep(20)
        async with aiohttp.ClientSession() as session:
            async with session.get("https://pay.crypt.bot/api/getInvoices", headers={"Crypto-Pay-API-Token": CRYPTO_TOKEN}) as resp:
                data = await resp.json()
        if data.get("ok"):
            async with aiosqlite.connect(DB_NAME) as db:
                for inv in data["result"]["items"]:
                    if inv["status"] == "paid":
                        async with db.execute("SELECT user_id, plan_id FROM crypto_invoices WHERE invoice_id=?", (str(inv["invoice_id"]),)) as cur:
                            row = await cur.fetchone()
                            if row:
                                await extend_user(row[0], PLANS[row[1]]["days"])
                                await bot.send_message(row[0], "✅ Оплата принята! Можешь вступать в канал.")
                                await db.execute("DELETE FROM crypto_invoices WHERE invoice_id=?", (str(inv["invoice_id"]),))
                                await db.commit()

async def main():
    await init_db()
    asyncio.create_task(check_crypto())
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
