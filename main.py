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

cursor.execute("""
CREATE TABLE IF NOT EXISTS referrals (
    user_id INTEGER,
    referred_id INTEGER UNIQUE
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
    "1": {"days": 1, "stars": 550, "crypto": 5},
    "7": {"days": 7, "stars": 770, "crypto": 7},
    "30": {"days": 30, "stars": 1100, "crypto": 10},
}

# ================== SAFE EDIT ==================
async def safe_edit(call: CallbackQuery, text: str, kb=None):
    try:
        await call.message.edit_text(text, reply_markup=kb)
    except:
        # если Telegram не даёт edit — просто отправляем новое
        await call.message.answer(text, reply_markup=kb)
    await call.answer()

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
    await safe_edit(call, MAIN_TEXT, menu())

# ================== STARS ==================
@router.callback_query(F.data == "stars")
async def stars(call: CallbackQuery):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="1 день", callback_data="stars:1")],
        [InlineKeyboardButton(text="7 дней", callback_data="stars:7")],
        [InlineKeyboardButton(text="30 дней", callback_data="stars:30")],
        [InlineKeyboardButton(text="⬅ Назад", callback_data="back")]
    ])

    await safe_edit(call, "⭐ Stars оплата\n\nВыбери тариф:", kb)

# ================== CRYPTO ==================
@router.callback_query(F.data == "crypto")
async def crypto(call: CallbackQuery):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="1 день", callback_data="crypto:1")],
        [InlineKeyboardButton(text="7 дней", callback_data="crypto:7")],
        [InlineKeyboardButton(text="30 дней", callback_data="crypto:30")],
        [InlineKeyboardButton(text="⬅ Назад", callback_data="back")]
    ])

    await safe_edit(call, "💰 Crypto оплата\n\nВыбери тариф:", kb)

# ================== PLAN STARS ==================
@router.callback_query(F.data.startswith("stars:"))
async def stars_plan(call: CallbackQuery):
    plan = call.data.split(":")[1]

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💳 Оплатить", callback_data=f"pay:stars:{plan}")],
        [InlineKeyboardButton(text="⬅ Назад", callback_data="stars")]
    ])

    await safe_edit(
        call,
        f"⭐ {plan} дней — {PLANS[plan]['stars']}⭐",
        kb
    )

# ================== PLAN CRYPTO ==================
@router.callback_query(F.data.startswith("crypto:"))
async def crypto_plan(call: CallbackQuery):
    plan = call.data.split(":")[1]

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💳 Оплатить", callback_data=f"pay:crypto:{plan}")],
        [InlineKeyboardButton(text="⬅ Назад", callback_data="crypto")]
    ])

    await safe_edit(
        call,
        f"💰 {plan} дней — {PLANS[plan]['crypto']} USDT",
        kb
    )

# ================== REF ==================
@router.callback_query(F.data == "ref")
async def ref(call: CallbackQuery):
    user_id = call.from_user.id
    link = f"https://t.me/{(await bot.get_me()).username}?start={user_id}"

    cursor.execute("SELECT COUNT(*) FROM referrals WHERE user_id=?", (user_id,))
    count = cursor.fetchone()[0]

    text = (
        "👥 РЕФЕРАЛЬНАЯ СИСТЕМА\n\n"
        "💡 Получи +7 дней:\n"
        "— у тебя должна быть подписка\n"
        "— пригласи друга\n"
        "— он оплачивает доступ\n\n"
        f"🔗 Твоя ссылка:\n{link}\n\n"
        f"👤 Приглашено: {count}"
    )

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅ Назад", callback_data="back")]
    ])

    await safe_edit(call, text, kb)

# ================== INFO ==================
@router.callback_query(F.data == "info")
async def info(call: CallbackQuery):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📄 Политика конфиденциальности", callback_data="privacy")],
        [InlineKeyboardButton(text="📜 Пользовательское соглашение", callback_data="terms")],
        [InlineKeyboardButton(text="⬅ Назад", callback_data="back")]
    ])

    await safe_edit(call, "ℹ️ Информация", kb)

# ================== PRIVACY FULL ==================
@router.callback_query(F.data == "privacy")
async def privacy(call: CallbackQuery):
    text = """Политика конфиденциальности
Platega • 1 апреля в 20:29

Данная Политика конфиденциальности регламентирует сбор идентификаторов аккаунта, технической информации и истории взаимодействий для обеспечения работы сервиса, связи с пользователем и аналитики. Передача данных третьим лицам допускается только по закону, для выполнения обязательств или с согласия пользователя.
Администрация хранит информацию необходимый срок, применяет разумные меры защиты, но не гарантирует абсолютной безопасности. Пользователь自行承担 риски передачи данных и принимает любые изменения в политике, продолжая использовать сервис.

Cocoon AI Summary
Политика регулирует сбор и использование данных для работы сервиса, связи и аналитики. Данные могут храниться и защищаются в разумных пределах.

1. Общие положения
2. Сбор информации
3. Использование информации
4. Передача информации
5. Хранение и защита
6. Ответственность
7. Изменения"""

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅ Назад", callback_data="info")]
    ])

    await safe_edit(call, text, kb)

# ================== TERMS FULL ==================
@router.callback_query(F.data == "terms")
async def terms(call: CallbackQuery):
    text = """Пользовательское соглашение
Platega • 1 апреля в 20:30

1. Общие положения
1.1. Пользователь подтверждает согласие с условиями.
1.2. Использование сервиса = принятие правил.

2. Услуги
2.1. Сервис предоставляет цифровые материалы.
2.2. Материалы могут быть информационными и авторскими.

3. Отказ от гарантий
3.1. Сервис предоставляется "как есть".
3.2. Нет гарантий результата.

4. Законность использования
4.1. Пользователь обязан соблюдать законы.

5. Интеллектуальная собственность
5.1. Материалы защищены правами.

6. Ограничение доступа
6.1. Доступ может быть ограничен.

7. Платежи
7.1. Возвраты не предусмотрены (кроме исключений).

8. Конфиденциальность
8.1. Минимальный сбор данных.

9. Изменения
9.1. Условия могут изменяться.

10. Контакты
10.1. Поддержка через бот."""

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅ Назад", callback_data="info")]
    ])

    await safe_edit(call, text, kb)

# ================== RUN ==================
async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
