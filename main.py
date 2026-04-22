import asyncio
import logging
import os
import sqlite3

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

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
router = Router()
dp.include_router(router)

# ================== DB ==================
conn = sqlite3.connect("users.db")
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    expire_date TEXT
)
""")

conn.commit()

# ================== TEXT ==================
MAIN_TEXT = (
    "👋 Привет, я Ева и это мой закрытый канал\n\n"
    "❓ Что внутри?\n\n"
    "Закрытый контент по подписке\n"
    "💎 Без ограничений\n"
    "🔥 Обновления регулярно\n\n"
    "Выбери способ оплаты 👇"
)

# ================== PLANS ==================
PLANS = {
    "1": {"stars": 550, "crypto": 5},
    "7": {"stars": 770, "crypto": 7},
    "30": {"stars": 1100, "crypto": 10},
}

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

# ================== CRYPTO ==================
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

# ================== CRYPTO PAY ==================
@router.callback_query(F.data.startswith("crypto:"))
async def crypto_pay(call: CallbackQuery):
    plan = call.data.split(":")[1]

    link = f"https://nowpayments.io/payment/?amount={PLANS[plan]['crypto']}&currency=USDT"

    await call.message.answer(f"💰 Оплата криптой:\n\n{link}")
    await call.answer()

# ================== REF ==================
@router.callback_query(F.data == "ref")
async def ref(call: CallbackQuery):
    text = (
        "👥 РЕФЕРАЛЬНАЯ СИСТЕМА\n\n"
        "Пригласи друга и получи +7 дней доступа\n\n"
        "Условия:\n"
        "— у тебя должна быть активная подписка\n"
        "— друг должен оплатить\n\n"
        f"Твоя ссылка:\nhttps://t.me/your_bot?start={call.from_user.id}"
    )

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅ Назад", callback_data="back")]
    ])

    await call.message.edit_text(text, reply_markup=kb)
    await call.answer()

# ================== INFO ==================
@router.callback_query(F.data == "info")
async def info(call: CallbackQuery):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📄 Политика конфиденциальности", callback_data="privacy")],
        [InlineKeyboardButton(text="📜 Пользовательское соглашение", callback_data="terms")],
        [InlineKeyboardButton(text="⬅ Назад", callback_data="back")]
    ])

    await call.message.edit_text("ℹ️ Информация", reply_markup=kb)
    await call.answer()

# ================== FULL PRIVACY ==================
@router.callback_query(F.data == "privacy")
async def privacy(call: CallbackQuery):

    text = """Политика конфиденциальности
Platega • 1 апреля в 20:29
Данная Политика конфиденциальности регламентирует сбор идентификаторов аккаунта, технической информации и истории взаимодействий для обеспечения работы сервиса, связи с пользователем и аналитики. Передача данных третьим лицам допускается только по закону, для выполнения обязательств или с согласия пользователя.
Администрация хранит информацию необходимый срок, применяет разумные меры защиты, но не гарантирует абсолютной безопасности. Пользователь自行承担 риски передачи данных и принимает любые изменения в политике, продолжая использовать сервис.
Cocoon AI Summary
Политика конфиденциальности регулирует сбор, использование и защиту информации пользователей сервиса. Собираются идентификаторы аккаунта, техническая информация и история взаимодействий. Данные используются для обеспечения работы сервиса, связи с пользователем и анализа. Передача информации третьим лицам возможна только в законодательно установленных случаях или с согласия пользователя. Хранение данных осуществляется в течение необходимого срока, их защита — в разумных пределах. Пользователь самостоятельно несёт ответственность за риски, связанные с передачей данных. Администрация вправе вносить изменения в Политику без уведомления — согласие считается принятым при дальнейшем использовании сервиса.

1. Общие положения
1.1. Политика регулирует обработку данных.
1.2. Использование сервиса означает согласие.

2. Сбор информации
2.1. ID, логин, устройство, IP.
2.2. Без паспортных данных.

3. Использование
3.1. Работа сервиса и поддержка.

4. Передача
4.1. Только по закону или с согласия.

5. Хранение
5.1. Пока нужно для сервиса.

6. Ответственность
6.1. Риски на пользователе.

7. Изменения
7.1. Возможны без уведомления.
"""

    await call.message.answer(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅ Назад", callback_data="info")]
    ]))
    await call.answer()

# ================== TERMS ==================
@router.callback_query(F.data == "terms")
async def terms(call: CallbackQuery):

    text = """Пользовательское соглашение
Platega • 1 апреля в 20:30
1. Общие положения
1.1. Использование сервиса = согласие.

2. Услуги
2.1. Цифровые материалы и доступ.

3. Ответственность
3.1. AS IS без гарантий.

4. Использование
4.1. Только законное применение.

5. Права
5.1. Материалы защищены.

6. Доступ
6.1. Может быть ограничен.

7. Платежи
7.1. Возврат ограничен.

8. Конфиденциальность
8.1. Минимальные данные.

9. Изменения
9.1. Возможны.

10. Контакты
10.1. Через бота.
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
