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
    ContentType,
)

logging.basicConfig(level=logging.INFO)

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CRYPTO_TOKEN = os.getenv("CRYPTO_TOKEN")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# ================= PRICES =================

STARS = {
    "1": 550,
    "7": 770,
    "30": 1100,
}

CRYPTO = {
    "1": 5,
    "7": 7,
    "30": 10,
}

# ================= MAIN MENU =================

def main_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="⭐ Stars", callback_data="stars"),
            InlineKeyboardButton(text="💰 Crypto", callback_data="crypto"),
        ]
    ])

# ================= STARS =================

def stars_menu_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="1 день — 550⭐", callback_data="s_1")],
        [InlineKeyboardButton(text="7 дней — 770⭐", callback_data="s_7")],
        [InlineKeyboardButton(text="30 дней — 1100⭐", callback_data="s_30")],
        [InlineKeyboardButton(text="⬅ Назад", callback_data="back_main")]
    ])

# ================= CRYPTO =================

def crypto_menu_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="1 день — 5 USDT", callback_data="c_1")],
        [InlineKeyboardButton(text="7 дней — 7 USDT", callback_data="c_7")],
        [InlineKeyboardButton(text="30 дней — 10 USDT", callback_data="c_30")],
        [InlineKeyboardButton(text="⬅ Назад", callback_data="back_main")]
    ])

# ================= START =================

@dp.message(F.text == "/start")
async def start(message: Message):
    await message.answer("🔒 Главное меню", reply_markup=main_kb())

# ================= BACK =================

@dp.callback_query(F.data == "back_main")
async def back(call: CallbackQuery):
    await call.message.edit_text("🔒 Главное меню", reply_markup=main_kb())
    await call.answer()

# ================= STARS MENU =================

@dp.callback_query(F.data == "stars")
async def stars_menu(call: CallbackQuery):
    await call.message.edit_text(
        "⭐ Stars оплата\n\nВыбери тариф:",
        reply_markup=stars_menu_kb()
    )
    await call.answer()

# ================= CRYPTO MENU =================

@dp.callback_query(F.data == "crypto")
async def crypto_menu(call: CallbackQuery):
    await call.message.edit_text(
        "💰 Crypto оплата\n\nВыбери тариф:",
        reply_markup=crypto_menu_kb()
    )
    await call.answer()

# ================= STARS PLAN =================

@dp.callback_query(F.data.startswith("s_"))
async def stars_plan(call: CallbackQuery):
    plan = call.data.split("_")[1]
    price = STARS[plan]

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💳 Перейти к оплате", callback_data=f"confirm_s_{plan}")],
        [InlineKeyboardButton(text="⬅ Назад", callback_data="stars")]
    ])

    await call.message.edit_text(
        f"⭐ Тариф: {plan} дней\nЦена: {price}⭐\n\nПодтверждение оплаты:",
        reply_markup=kb
    )
    await call.answer()

# ================= STARS CONFIRM =================

@dp.callback_query(F.data.startswith("confirm_s_"))
async def stars_confirm(call: CallbackQuery):
    plan = call.data.split("_")[2]
    price = STARS[plan]

    await bot.send_invoice(
        chat_id=call.message.chat.id,
        title=f"{plan} дней доступа",
        description="Оплата Stars",
        payload=f"stars_{plan}",
        provider_token="",
        currency="XTR",
        prices=[LabeledPrice(label="Access", amount=price)]
    )

    await call.answer()

# ================= CRYPTO PLAN =================

@dp.callback_query(F.data.startswith("c_"))
async def crypto_plan(call: CallbackQuery):
    plan = call.data.split("_")[1]
    price = CRYPTO[plan]

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💳 Создать инвойс", callback_data=f"confirm_c_{plan}")],
        [InlineKeyboardButton(text="⬅ Назад", callback_data="crypto")]
    ])

    await call.message.edit_text(
        f"💰 Тариф: {plan} дней\nЦена: {price} USDT\n\nПодтверждение:",
        reply_markup=kb
    )
    await call.answer()

# ================= CRYPTO CREATE INVOICE =================

def create_invoice(amount, label):
    url = "https://pay.crypt.bot/api/createInvoice"
    headers = {"Crypto-Pay-API-Token": CRYPTO_TOKEN}
    data = {
        "asset": "USDT",
        "amount": amount,
        "description": label,
    }

    r = requests.post(url, headers=headers, json=data)
    return r.json()["result"]

# ================= CRYPTO CONFIRM =================

@dp.callback_query(F.data.startswith("confirm_c_"))
async def crypto_confirm(call: CallbackQuery):
    plan = call.data.split("_")[2]
    amount = CRYPTO[plan]

    invoice = create_invoice(amount, f"{plan}_days")

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Я оплатил ✅", callback_data=f"check_{invoice['invoice_id']}")],
        [InlineKeyboardButton(text="⬅ Назад", callback_data="crypto")]
    ])

    await call.message.answer(
        f"💰 Оплата:\n{invoice['pay_url']}",
        reply_markup=kb
    )

    await call.answer()

# ================= CHECK PAYMENT =================

def check_invoice(invoice_id):
    url = "https://pay.crypt.bot/api/getInvoices"
    headers = {"Crypto-Pay-API-Token": CRYPTO_TOKEN}
    params = {"invoice_ids": invoice_id}

    r = requests.get(url, headers=headers, params=params)
    return r.json()["result"]["items"][0]["status"]

@dp.callback_query(F.data.startswith("check_"))
async def check_payment(call: CallbackQuery):
    invoice_id = call.data.split("_")[1]

    status = check_invoice(invoice_id)

    if status != "paid":
        await call.answer("Не оплачено ❌", show_alert=True)
        return

    await call.message.answer("✅ Оплата подтверждена")
    await call.answer()

# ================= STARS SUCCESS =================

@dp.message(F.content_type == ContentType.SUCCESSFUL_PAYMENT)
async def stars_success(message: Message):
    await message.answer("⭐ Stars оплата прошла!")

# ================= RUN =================

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
