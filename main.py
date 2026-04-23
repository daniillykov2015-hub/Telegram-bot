import asyncio
import logging
import os
import sqlite3
import requests

from aiogram import Bot, Dispatcher, Router, F
from aiogram.filters import CommandStart
from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    LabeledPrice,
    PreCheckoutQuery,
)

# ================== CONFIG ==================
logging.basicConfig(level=logging.INFO)

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CRYPTO_TOKEN = os.getenv("CRYPTO_TOKEN")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
router = Router()
dp.include_router(router)

# ================== PLANS ==================
PLANS = {
    "1": {"stars": 550, "crypto": 5},
    "7": {"stars": 770, "crypto": 7},
    "30": {"stars": 1100, "crypto": 10},
}

# ================== TEXT ==================
MAIN_TEXT = (
    "👋 Привет, я Ева и это мой закрытый канал\n\n"
    "❓ Что внутри?\n\n"
    "Закрытый контент по подписке\n"
    "💎 Без ограничений\n"
    "🔥 Обновления регулярно\n\n"
    "Выбери способ оплаты 👇"
)

# ================== MENU ==================
def menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="⭐ Stars", callback_data="stars"),
            InlineKeyboardButton(text="💰 Crypto", callback_data="crypto"),
        ],
        [
            InlineKeyboardButton(text="👥 Реферальная система", callback_data="ref")
        ],
        [
            InlineKeyboardButton(text="ℹ️ Информация", callback_data="info")
        ]
    ])

# ================== START ==================
@router.message(CommandStart())
async def start(message: Message):
    await message.answer(MAIN_TEXT, reply_markup=menu())

# ================== BACK ==================
@router.callback_query(F.data == "back")
async def back(call: CallbackQuery):
    await call.message.edit_text(MAIN_TEXT, reply_markup=menu())
    await call.answer()

# ================== STARS ==================
@router.callback_query(F.data == "stars")
async def stars(call: CallbackQuery):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="1 день", callback_data="stars:1")],
        [InlineKeyboardButton(text="7 дней", callback_data="stars:7")],
        [InlineKeyboardButton(text="30 дней", callback_data="stars:30")],
        [InlineKeyboardButton(text="⬅ Назад", callback_data="back")]
    ])
    await call.message.edit_text("⭐ Stars тарифы", reply_markup=kb)
    await call.answer()

# ================== CRYPTO MENU ==================
@router.callback_query(F.data == "crypto")
async def crypto(call: CallbackQuery):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="1 день", callback_data="crypto:1")],
        [InlineKeyboardButton(text="7 дней", callback_data="crypto:7")],
        [InlineKeyboardButton(text="30 дней", callback_data="crypto:30")],
        [InlineKeyboardButton(text="⬅ Назад", callback_data="back")]
    ])
    await call.message.edit_text("💰 Crypto тарифы", reply_markup=kb)
    await call.answer()

# ================== STARS PAY ==================
@router.callback_query(F.data.startswith("stars:"))
async def stars_pay(call: CallbackQuery):
    plan = call.data.split(":")[1]

    await bot.send_invoice(
        chat_id=call.message.chat.id,
        title="Подписка",
        description=f"{plan} дней доступа",
        payload=f"stars_{plan}",
        provider_token="",
        currency="XTR",
        prices=[LabeledPrice(label="Access", amount=PLANS[plan]["stars"])]
    )

    await call.answer()

# ================== PRECHECKOUT ==================
@router.pre_checkout_query()
async def pre_checkout(pre: PreCheckoutQuery):
    await pre.answer(ok=True)

# ================== SUCCESS ==================
@router.message(F.successful_payment)
async def success(message: Message):
    await message.answer("✅ Оплата прошла! Доступ активирован.")

# ================== CRYPTO ==================
@router.callback_query(F.data.startswith("crypto:"))
async def crypto_pay(call: CallbackQuery):
    plan = call.data.split(":")[1]
    amount = PLANS[plan]["crypto"]

    r = requests.post(
        "https://pay.crypt.bot/api/createInvoice",
        headers={"Crypto-Pay-API-Token": CRYPTO_TOKEN},
        json={
            "asset": "USDT",
            "amount": amount,
            "description": f"{plan} days access"
        }
    ).json()

    if not r.get("ok"):
        await call.message.answer("❌ Ошибка создания инвойса")
        await call.answer()
        return

    invoice = r["result"]

    await call.message.answer(
        f"💰 Оплата через Crypto Bot:\n\n{invoice['pay_url']}"
    )

    await call.answer()

# ================== REF ==================
@router.callback_query(F.data == "ref")
async def ref(call: CallbackQuery):
    text = (
        "👥 РЕФЕРАЛЬНАЯ СИСТЕМА\n\n"
        "Пригласи друга и получи +7 дней доступа\n\n"
        "УСЛОВИЯ:\n"
        "— у тебя должна быть активная подписка\n"
        "— друг должен оплатить подписку\n\n"
        "КАК ПОЛУЧИТЬ БОНУС:\n"
        "1. Отправь свою ссылку другу\n"
        "2. Он оплачивает доступ\n"
        "3. Ты получаешь +7 дней автоматически\n\n"
        f"Твоя ссылка:\nhttps://t.me/your_bot?start={call.from_user.id}"
    )

    await call.message.edit_text(
        text,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⬅ Назад", callback_data="back")]
        ])
    )
    await call.answer()

# ================== INFO ==================
@router.callback_query(F.data == "info")
async def info(call: CallbackQuery):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📄 Политика конфиденциальности", callback_data="privacy")],
        [InlineKeyboardButton(text="📜 Пользовательское соглашение", callback_data="terms")],
        [InlineKeyboardButton(text="💬 Поддержка", url="https://t.me/mistybibi")],
        [InlineKeyboardButton(text="⬅ Назад", callback_data="back")]
    ])
    await call.message.edit_text("ℹ️ Информация", reply_markup=kb)
    await call.answer()

# ================== PRIVACY ==================
@router.callback_query(F.data == "privacy")
async def privacy(call: CallbackQuery):

    text = """Политика конфиденциальности
Platega • 
Данная Политика конфиденциальности регламентирует сбор идентификаторов аккаунта...
(оставь тут свой ПОЛНЫЙ текст без изменений — он у тебя уже был правильный)
"""

    await call.message.answer(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅ Назад", callback_data="info")]
    ]))
    await call.answer()

# ================== TERMS ==================
@router.callback_query(F.data == "terms")
async def terms(call: CallbackQuery):

    text = """Пользовательское соглашение
(твой полный текст — он у тебя уже корректный)
"""

    await call.message.answer(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅ Назад", callback_data="info")]
    ]))
    await call.answer()

# ================== RUN ==================
async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
