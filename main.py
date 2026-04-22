import asyncio
import logging
import os
import requests

from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, LabeledPrice

logging.basicConfig(level=logging.INFO)

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CRYPTO_TOKEN = os.getenv("CRYPTO_TOKEN")

bot = Bot(token=TOKEN)
dp = Dispatcher()

# ---------------- ТАРИФЫ ---------------- #

PLANS = {
    "1": {
        "days": 1,
        "stars": 550,
        "crypto": 5,
        "title": "1 день доступа"
    },
    "7": {
        "days": 7,
        "stars": 770,
        "crypto": 7,
        "title": "7 дней доступа"
    },
    "30": {
        "days": 30,
        "stars": 1100,
        "crypto": 10,
        "title": "30 дней доступа"
    },
}

# ---------------- КНОПКИ ---------------- #

def main_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⭐ Stars", callback_data="stars")],
        [InlineKeyboardButton(text="💰 Crypto", callback_data="crypto")],
        [InlineKeyboardButton(text="ℹ Info", callback_data="info")]
    ])


def plans_kb(prefix: str):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="1 день", callback_data=f"{prefix}_1")],
        [InlineKeyboardButton(text="7 дней", callback_data=f"{prefix}_7")],
        [InlineKeyboardButton(text="30 дней", callback_data=f"{prefix}_30")],
        [InlineKeyboardButton(text="⬅ Назад", callback_data="back")]
    ])

# ---------------- CRYPTO ---------------- #

def create_invoice(amount, payload):
    url = "https://pay.crypt.bot/api/createInvoice"
    headers = {"Crypto-Pay-API-Token": CRYPTO_TOKEN}

    r = requests.post(url, headers=headers, json={
        "asset": "USDT",
        "amount": amount,
        "description": payload
    })

    return r.json()["result"]

# ---------------- START ---------------- #

@dp.message(Command("start"))
async def start(message: Message):
    await message.answer(
        "🔒 Добро пожаловать\nВыбери оплату:",
        reply_markup=main_kb()
    )

# ---------------- MENU ---------------- #

@dp.callback_query(F.data == "stars")
async def stars(call: CallbackQuery):
    await call.message.edit_text("⭐ Оплата Stars", reply_markup=plans_kb("s"))


@dp.callback_query(F.data == "crypto")
async def crypto(call: CallbackQuery):
    await call.message.edit_text("💰 Оплата Crypto", reply_markup=plans_kb("c"))


@dp.callback_query(F.data == "back")
async def back(call: CallbackQuery):
    await call.message.edit_text("Главное меню", reply_markup=main_kb())


# ---------------- STARS ---------------- #

@dp.callback_query(F.data.startswith("s_"))
async def pay_stars(call: CallbackQuery):
    plan = PLANS[call.data.split("_")[1]]

    await bot.send_invoice(
        chat_id=call.message.chat.id,
        title=plan["title"],
        description="Доступ в закрытый канал",
        payload=f"stars_{plan['days']}",
        provider_token="",
        currency="XTR",
        prices=[LabeledPrice(label="Доступ", amount=plan["stars"])]
    )

    await call.answer()


# ---------------- CRYPTO ---------------- #

@dp.callback_query(F.data.startswith("c_"))
async def pay_crypto(call: CallbackQuery):
    plan = PLANS[call.data.split("_")[1]]

    invoice = create_invoice(plan["crypto"], f"{plan['days']}_days")

    await call.message.answer(
        "💰 Оплата криптой\n\n"
        f"Срок: {plan['days']} дней\n"
        f"Сумма: {plan['crypto']} USDT\n\n"
        f"Ссылка:\n{invoice['pay_url']}"
    )

    await call.answer()


# ---------------- INFO ---------------- #

@dp.callback_query(F.data == "info")
async def info(call: CallbackQuery):
    await call.message.edit_text(
        "ℹ Бот работает на aiogram v3\n"
        "⭐ Stars + 💰 Crypto оплаты\n\n"
        "Тарифы:\n"
        "1д — 550⭐ / 5 USDT\n"
        "7д — 770⭐ / 7 USDT\n"
        "30д — 1100⭐ / 10 USDT",
        reply_markup=main_kb()
    )


# ---------------- RUN ---------------- #

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
