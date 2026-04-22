import asyncio
import logging
import os
import requests

from aiogram import Bot, Dispatcher, F
from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    LabeledPrice,
    ContentType
)

logging.basicConfig(level=logging.INFO)

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CRYPTO_TOKEN = os.getenv("CRYPTO_TOKEN")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# ================== ЦЕНЫ ==================

STARS = {
    "1": 550,
    "7": 770,
    "30": 1100
}

CRYPTO = {
    "1": 5,
    "7": 7,
    "30": 10
}

# ================== KEYBOARDS ==================

def main_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="⭐ Stars", callback_data="stars"),
            InlineKeyboardButton(text="💰 Crypto", callback_data="crypto"),
        ]
    ])


def back_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅ Назад", callback_data="back")]
    ])


# ================== START ==================

@dp.message(F.text == "/start")
async def start(message: Message):
    await message.answer(
        "🔒 Меню оплаты",
        reply_markup=main_kb()
    )


# ================== BACK ==================

@dp.callback_query(F.data == "back")
async def back(call: CallbackQuery):
    await call.message.edit_text(
        "🔒 Меню оплаты",
        reply_markup=main_kb()
    )
    await call.answer()


# ================== MENU ==================

@dp.callback_query(F.data == "stars")
async def stars_menu(call: CallbackQuery):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="1 день — 550⭐", callback_data="s_1")],
        [InlineKeyboardButton(text="7 дней — 770⭐", callback_data="s_7")],
        [InlineKeyboardButton(text="30 дней — 1100⭐", callback_data="s_30")],
        [InlineKeyboardButton(text="⬅ Назад", callback_data="back")]
    ])

    await call.message.edit_text("⭐ Оплата Stars", reply_markup=kb)
    await call.answer()


@dp.callback_query(F.data == "crypto")
async def crypto_menu(call: CallbackQuery):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="1 день — 5 USDT", callback_data="c_1")],
        [InlineKeyboardButton(text="7 дней — 7 USDT", callback_data="c_7")],
        [InlineKeyboardButton(text="30 дней — 10 USDT", callback_data="c_30")],
        [InlineKeyboardButton(text="⬅ Назад", callback_data="back")]
    ])

    await call.message.edit_text("💰 Crypto оплата", reply_markup=kb)
    await call.answer()


# ================== STARS PAYMENT ==================

@dp.callback_query(F.data.startswith("s_"))
async def pay_stars(call: CallbackQuery):
    plan = call.data.split("_")[1]
    price = STARS[plan]

    await bot.send_invoice(
        chat_id=call.message.chat.id,
        title=f"{plan} дней доступа",
        description="Оплата через Telegram Stars",
        payload=f"stars_{plan}",
        provider_token="",  # важно: пусто для Stars
        currency="XTR",
        prices=[LabeledPrice(label="Доступ", amount=price)]
    )

    await call.answer()


# ================== CRYPTO PAYMENT ==================

def create_invoice(amount, label):
    url = "https://pay.crypt.bot/api/createInvoice"
    headers = {"Crypto-Pay-API-Token": CRYPTO_TOKEN}
    data = {
        "asset": "USDT",
        "amount": amount,
        "description": label
    }

    r = requests.post(url, headers=headers, json=data)
    return r.json()["result"]


@dp.callback_query(F.data.startswith("c_"))
async def pay_crypto(call: CallbackQuery):
    plan = call.data.split("_")[1]
    amount = CRYPTO[plan]

    invoice = create_invoice(amount, f"{plan} days")

    pay_url = invoice["pay_url"]
    invoice_id = invoice["invoice_id"]

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Я оплатил ✅", callback_data=f"check_{invoice_id}")]
    ])

    await call.message.answer(
        f"💰 Оплатите по ссылке:\n{pay_url}",
        reply_markup=kb
    )

    await call.answer()


# ================== CHECK CRYPTO ==================

def check_invoice(invoice_id):
    url = "https://pay.crypt.bot/api/getInvoices"
    headers = {"Crypto-Pay-API-Token": CRYPTO_TOKEN}
    params = {"invoice_ids": invoice_id}

    r = requests.get(url, headers=headers, params=params)
    return r.json()["result"]["items"][0]["status"]


@dp.callback_query(F.data.startswith("check_"))
async def check_pay(call: CallbackQuery):
    invoice_id = call.data.split("_")[1]

    status = check_invoice(invoice_id)

    if status != "paid":
        await call.answer("Платёж не найден ❌", show_alert=True)
        return

    await call.message.answer("✅ Оплата прошла! Доступ выдан.")
    await call.answer()


# ================== STARS SUCCESS ==================

@dp.pre_checkout_query()
async def checkout(pre_checkout):
    await bot.answer_pre_checkout_query(pre_checkout.id, ok=True)


@dp.message(F.content_type == ContentType.SUCCESSFUL_PAYMENT)
async def success(message: Message):
    await message.answer("⭐ Оплата Stars прошла! Доступ выдан.")


# ================== RUN ==================

async def main():
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
