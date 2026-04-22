import asyncio
import logging
import os
from aiogram import Bot, Dispatcher, F
from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)

logging.basicConfig(level=logging.INFO)

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# ====== ЦЕНЫ (как у тебя было) ======
STARS_PRICES = {
    "1": 550,
    "7": 770,
    "30": 1100
}

CRYPTO_PRICES = {
    "1": 5,
    "7": 7,
    "30": 10
}


# ================= KEYBOARDS =================

def main_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="⭐ Оплата Stars", callback_data="stars_menu"),
            InlineKeyboardButton(text="💰 Crypto", callback_data="crypto_menu"),
        ],
        [
            InlineKeyboardButton(text="📅 Подписка", callback_data="sub_menu"),
        ]
    ])


def back_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅ Назад", callback_data="back_main")]
    ])


def stars_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="1 день — 550⭐", callback_data="s_1")],
        [InlineKeyboardButton(text="7 дней — 770⭐", callback_data="s_7")],
        [InlineKeyboardButton(text="30 дней — 1100⭐", callback_data="s_30")],
        [InlineKeyboardButton(text="⬅ Назад", callback_data="back_main")]
    ])


def crypto_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="1 день — 5 USDT", callback_data="c_1")],
        [InlineKeyboardButton(text="7 дней — 7 USDT", callback_data="c_7")],
        [InlineKeyboardButton(text="30 дней — 10 USDT", callback_data="c_30")],
        [InlineKeyboardButton(text="⬅ Назад", callback_data="back_main")]
    ])


def pay_back_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅ Назад", callback_data="back_main")]
    ])


# ================= START =================

@dp.message(F.text == "/start")
async def start(message: Message):
    await message.answer(
        "🔒 Добро пожаловать\n\nВыбери оплату:",
        reply_markup=main_kb()
    )


# ================= MAIN MENU =================

@dp.callback_query(F.data == "back_main")
async def back(call: CallbackQuery):
    await call.message.edit_text(
        "🔒 Главное меню",
        reply_markup=main_kb()
    )
    await call.answer()


@dp.callback_query(F.data == "stars_menu")
async def stars_menu(call: CallbackQuery):
    await call.message.edit_text(
        "⭐ Оплата Telegram Stars\n\nВыбери тариф:",
        reply_markup=stars_kb()
    )
    await call.answer()


@dp.callback_query(F.data == "crypto_menu")
async def crypto_menu(call: CallbackQuery):
    await call.message.edit_text(
        "💰 Оплата Crypto\n\nВыбери тариф:",
        reply_markup=crypto_kb()
    )
    await call.answer()


# ================= STARS =================

@dp.callback_query(F.data.startswith("s_"))
async def stars_pay(call: CallbackQuery):
    plan = call.data.split("_")[1]

    price = STARS_PRICES[plan]

    await call.message.edit_text(
        f"⭐ Оплата Stars\n\nТариф: {plan} день(дней)\nЦена: {price}⭐\n\n(тут будет твоя логика оплаты)",
        reply_markup=pay_back_kb()
    )
    await call.answer()


# ================= CRYPTO =================

@dp.callback_query(F.data.startswith("c_"))
async def crypto_pay(call: CallbackQuery):
    plan = call.data.split("_")[1]

    price = CRYPTO_PRICES[plan]

    await call.message.edit_text(
        f"💰 Crypto оплата\n\nТариф: {plan} день(дней)\nЦена: {price} USDT\n\n(тут будет создание инвойса)",
        reply_markup=pay_back_kb()
    )
    await call.answer()


# ================= RUN =================

async def main():
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
