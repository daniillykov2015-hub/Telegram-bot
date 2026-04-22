import asyncio
import logging
import os
import requests
from datetime import datetime, timedelta

from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, CallbackQuery
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command

logging.basicConfig(level=logging.INFO)

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CRYPTO_TOKEN = os.getenv("CRYPTO_TOKEN")

bot = Bot(token=TOKEN)
dp = Dispatcher()

# ---------------- PAYMENTS ---------------- #

PLANS = {
    "1": {"days": 1, "stars": 550, "crypto": 5},
    "7": {"days": 7, "stars": 770, "crypto": 7},
    "30": {"days": 30, "stars": 1100, "crypto": 10},
}


def crypto_create_invoice(amount, payload):
    url = "https://pay.crypt.bot/api/createInvoice"
    headers = {"Crypto-Pay-API-Token": CRYPTO_TOKEN}

    r = requests.post(url, headers=headers, json={
        "asset": "USDT",
        "amount": amount,
        "description": payload
    })

    data = r.json()
    return data["result"]


def crypto_check(invoice_id):
    url = "https://pay.crypt.bot/api/getInvoices"
    headers = {"Crypto-Pay-API-Token": CRYPTO_TOKEN}

    r = requests.get(url, headers=headers, params={"invoice_ids": invoice_id})
    data = r.json()

    return data["result"]["items"][0]["status"]


# ---------------- UI ---------------- #

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


# ---------------- START ---------------- #

@dp.message(Command("start"))
async def start(message: Message):
    await message.answer(
        "🔒 Добро пожаловать\nВыбери оплату:",
        reply_markup=main_kb()
    )


# ---------------- MENU ---------------- #

@dp.callback_query(F.data == "stars")
async def stars_menu(call: CallbackQuery):
    await call.message.edit_text("⭐ Оплата Stars", reply_markup=plans_kb("s"))


@dp.callback_query(F.data == "crypto")
async def crypto_menu(call: CallbackQuery):
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
        title=f"{plan['days']} дня доступа",
        description="Stars payment",
        payload=f"stars_{plan['days']}",
        provider_token="",
        currency="XTR",
        prices=[{"label": "Access", "amount": plan["stars"]}]
    )


# ---------------- CRYPTO ---------------- #

@dp.callback_query(F.data.startswith("c_"))
async def pay_crypto(call: CallbackQuery):
    plan = PLANS[call.data.split("_")[1]]

    invoice = crypto_create_invoice(plan["crypto"], f"{plan['days']}_days")

    await call.message.answer(
        f"💰 Оплати:\n{invoice['pay_url']}"
    )

    await call.message.answer("После оплаты нажми /check")


# ---------------- CHECK ---------------- #

@dp.message(Command("check"))
async def check(message: Message):
    # упрощённая версия (в реале храни invoice_id в БД)
    await message.answer("⏳ Проверка оплаты (заглушка для core v3)")


# ---------------- INFO ---------------- #

@dp.callback_query(F.data == "info")
async def info(call: CallbackQuery):
    await call.message.edit_text(
        "ℹ Бот работает на aiogram v3\n"
        "Stars + Crypto payments",
        reply_markup=main_kb()
    )


# ---------------- RUN ---------------- #

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
