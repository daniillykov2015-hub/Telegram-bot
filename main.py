import asyncio
import logging
import os
import aiohttp
import sqlite3
from datetime import datetime, timedelta

from aiogram import Bot, Dispatcher, Router, F
from aiogram.filters import CommandStart, CommandObject
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
CHANNEL_ID = -1002061036324  # Убедитесь, что это верный ID канала

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
router = Router()
dp.include_router(router)

# ================== DATABASE ==================
def init_db():
    conn = sqlite3.connect("database.db")
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            referrer_id INTEGER,
            expiry_date TEXT,
            is_active INTEGER DEFAULT 0
        )
    """)
    conn.commit()
    conn.close()

def add_user(user_id, referrer_id=None):
    conn = sqlite3.connect("database.db")
    cur = conn.cursor()
    cur.execute("INSERT OR IGNORE INTO users (user_id, referrer_id) VALUES (?, ?)", (user_id, referrer_id))
    conn.commit()
    conn.close()

def activate_subscription(user_id, days):
    conn = sqlite3.connect("database.db")
    cur = conn.cursor()
    cur.execute("SELECT expiry_date FROM users WHERE user_id = ?", (user_id,))
    res = cur.fetchone()
    now = datetime.now()
    if res and res[0]:
        current_expiry = datetime.strptime(res[0], "%Y-%m-%d %H:%M:%S")
        new_expiry = max(now, current_expiry) + timedelta(days=days)
    else:
        new_expiry = now + timedelta(days=days)
    cur.execute("UPDATE users SET expiry_date = ?, is_active = 1 WHERE user_id = ?", 
                (new_expiry.strftime("%Y-%m-%d %H:%M:%S"), user_id))
    cur.execute("SELECT referrer_id FROM users WHERE user_id = ?", (user_id,))
    ref_res = cur.fetchone()
    ref_id = ref_res[0] if ref_res else None
    conn.commit()
    conn.close()
    return ref_id

# ================== PLANS ==================
PLANS = {
    "1": {"stars": 550, "crypto": 5, "name": "1 день", "days": 1},
    "7": {"stars": 770, "crypto": 7, "name": "7 дней", "days": 7},
    "30": {"stars": 1100, "crypto": 10, "name": "30 дней", "days": 30},
}

# ================== TEXTS (ВАШИ ИСХОДНЫЕ) ==================
MAIN_TEXT = (
    "👋 Привет, я Ева и это мой закрытый канал\n\n"
    "❓ Что внутри?\n\n"
    "Закрытый контент по подписке\n"
    "💎 Без ограничений\n"
    "🔥 Обновления регулярно\n\n"
    "Выбери способ оплаты 👇"
)

PRIVACY_TEXT = """Политика конфиденциальности
Platega • 
Данная Политика конфиденциальности регламентирует сбор идентификаторов аккаунта, технической информации и истории взаимодействий для обеспечения работы сервиса, связи с пользователем и аналитики. Передача данных третьим лицам допускается только по закону, для выполнения обязательств или с согласия пользователя.
Администрация хранит информацию необходимый срок, применяет разумные меры защиты, но не гарантирует абсолютной безопасности. Пользователь самостоятельно несёт ответственность за риски, связанные с передачей данных и принимает любые изменения в политике, продолжая использовать сервис.

1. Общие положения
 1.1. Настоящая Политика конфиденциальности (далее — «Политика») регулирует порядок обработки и защиты информации, которую Пользователь передаёт при использовании сервиса (далее — «Сервис»).
 1.2. Используя Сервис, Пользователь подтверждает своё согласие с условиями Политики. Если Пользователь не согласен с условиями — он обязан прекратить использование Сервиса.

2. Сбор информации
 2.1. Сервис может собирать следующие типы данных:
 идентификаторы аккаунта (логин, ID, никнейм и т.п.);
 техническую информацию (IP-адрес, данные о браузере, устройстве и операционной системе);
 истории взаимодействий с Сервисом.
 2.2. Сервис не требует от Пользователя предоставления паспортных данных, документов, фотографий или другой личной информации, кроме минимально необходимой для работы.

3. Использование информации
 3.1. Сервис может использовать полученную информацию исключительно для:
 обеспечения работы функционала;
 связи с Пользователем (в том числе для уведомлений и поддержки);
 анализа и улучшения работы Сервиса.

4. Передача информации третьим лицам
 4.1. Администрация не передаёт полученные данные третьим лицам, за исключением случаев:
 если это требуется по закону;
 если это необходимо для исполнения обязательств перед Пользователем (например, при работе с платёжными системами);
 если Пользователь сам дал на это согласие.

5. Хранение и защита данных
 5.1. Данные хранятся в течение срока, необходимого для достижения целей обработки.
 5.2. Администрация принимает разумные меры для защиты данных, но не гарантирует абсолютную безопасность информации при передаче через интернет.

6. Отказ от ответственности
 6.1. Пользователь понимает и соглашается, что передача информации через интернет всегда сопряжена с рисками.
 6.2. Администрация не несёт ответственности за утрату, кражу или раскрытие данных, если это произошло по вине третьих лиц или самого Пользователя.

7. Изменения в Политике
 7.1. Администрация вправе изменять условия Политики без предварительного уведомления.
 7.2. Продолжение использования Сервиса после внесения изменений означает согласие Пользователя с новой редакцией Политики."""

TERMS_TEXT = """Пользовательское соглашение
Platega

1. Общие положения
1.1. Настоящее Пользовательское соглашение (далее — «Соглашение») регулирует порядок использования онлайн-сервиса (далее — «Сервис»), предоставляемого Администрацией.
1.2. Используя Сервис, включая запуск бота, регистрацию, оплату услуг или получение доступа к материалам, Пользователь подтверждает, что полностью ознакомился с условиями настоящего Соглашения и принимает их в полном объёме.
1.3. В случае несогласия с условиями Соглашения Пользователь обязан прекратить использование Сервиса.

2. Характер услуг и цифровых товаров
2.1. Сервис предоставляет цифровые товары и услуги нематериального характера, включая информационные материалы, обучающие материалы, консультации, цифровые продукты и сервисные услуги.
2.2. Материалы могут включать информацию из открытых источников, авторские материалы Администрации, аналитические обзоры, подборки и рекомендации.
2.3. Пользователь понимает, что ценность Сервиса заключается в структуре, подаче и обработке информации, а не в уникальности отдельных данных.
2.4. Сервис не гарантирует эксклюзивность или уникальность материалов вне платформы.

3. Отказ от гарантий и ответственности
3.1. Сервис предоставляется на условиях «AS IS» («как есть»).
3.2. Администрация не гарантирует достижение результатов, соответствие ожиданиям или бесперебойную работу.
3.3. Администрация не несёт ответственности за любые убытки, потерю данных, действия Пользователя, действия третьих лиц или технические сбои.

4. Законность использования
4.1. Пользователь обязуется не использовать Сервис в противоправных целях.
4.2. Ответственность за использование Сервиса полностью лежит на Пользователе.

5. Интеллектуальная собственность
5.1. Все материалы защищены авторским правом.
5.2. Запрещено копирование, распространение и перепродажа без разрешения.

6. Ограничение доступа
6.1. Администрация вправе ограничить или прекратить доступ к Сервису в любое время.
6.2. Обязательства Пользователя при этом сохраняются.

7. Платежи и возвраты
7.1. Доступ предоставляется после оплаты.
7.2. Возврат средств не предусмотрен, кроме случаев, когда услуга не была оказана.
7.3. Запрещены chargeback без обращения в поддержку.

8. Конфиденциальность
8.1. Сервис собирает минимальную информацию.
8.2. Полной безопасности в интернете не гарантируется.

9. Изменение условий
9.1. Условия могут изменяться.
9.2. Использование = согласие.

10. Контакты
10.1. Поддержка через бота.
Пользователь подтверждает согласие с условиями."""

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
async def start(message: Message, command: CommandObject):
    ref_id = None
    if command.args and command.args.isdigit():
        ref_id = int(command.args)
    add_user(message.from_user.id, ref_id)
    await message.answer(MAIN_TEXT, reply_markup=menu())

@router.callback_query(F.data == "back")
async def back(call: CallbackQuery):
    await call.message.edit_text(MAIN_TEXT, reply_markup=menu())
    await call.answer()

# --- STARS & CRYPTO ---

@router.callback_query(F.data == "stars")
async def stars_menu(call: CallbackQuery):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="1 день — 550 ⭐", callback_data="stars_confirm:1")],
        [InlineKeyboardButton(text="7 дней — 770 ⭐", callback_data="stars_confirm:7")],
        [InlineKeyboardButton(text="30 дней — 1100 ⭐", callback_data="stars_confirm:30")],
        [InlineKeyboardButton(text="⬅ Назад", callback_data="back")]
    ])
    await call.message.edit_text("⭐ Выберите период подписки Stars:", reply_markup=kb)

@router.callback_query(F.data.startswith("stars_confirm:"))
async def stars_confirm(call: CallbackQuery):
    plan_id = call.data.split(":")[1]
    plan = PLANS[plan_id]
    invoice_link = await bot.create_invoice_link(
        title="Подписка", description=f"Доступ на {plan['name']}",
        payload=f"plan_{plan_id}", provider_token="", currency="XTR",
        prices=[LabeledPrice(label="Оплата Stars", amount=plan['stars'])]
    )
    text = (f"<b>Проверьте детали платежа:</b>\n\n📦 Тариф: {plan['name']}\n💳 Способ оплаты: Stars\n💰 К оплате: {plan['stars']} ⭐")
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="💸 Оплатить", url=invoice_link)], [InlineKeyboardButton(text="⬅ Назад", callback_data="stars")]])
    await call.message.edit_text(text, reply_markup=kb, parse_mode="HTML")

@router.callback_query(F.data == "crypto")
async def crypto_menu(call: CallbackQuery):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="1 день — 5$", callback_data="crypto_confirm:1")],
        [InlineKeyboardButton(text="7 дней — 7$", callback_data="crypto_confirm:7")],
        [InlineKeyboardButton(text="30 дней — 10$", callback_data="crypto_confirm:30")],
        [InlineKeyboardButton(text="⬅ Назад", callback_data="back")]
    ])
    await call.message.edit_text("💰 Выберите тариф Crypto (USDT):", reply_markup=kb)

@router.callback_query(F.data.startswith("crypto_confirm:"))
async def crypto_confirm(call: CallbackQuery):
    plan_id = call.data.split(":")[1]
    plan = PLANS[plan_id]
    async with aiohttp.ClientSession() as session:
        async with session.post("https://pay.crypt.bot/api/createInvoice", headers={"Crypto-Pay-API-Token": CRYPTO_TOKEN},
                                json={"asset": "USDT", "amount": str(plan["crypto"]), "description": f"plan_{plan_id}"}) as resp:
            r = await resp.json()
    if r.get("ok"):
        pay_url = r["result"]["pay_url"]
        text = (f"<b>Проверьте детали платежа:</b>\n\n📦 Тариф: {plan['name']}\n💳 Способ оплаты: CryptoBot\n💰 К оплате: {plan['crypto']} $")
        kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="💸 Оплатить", url=pay_url)], [InlineKeyboardButton(text="⬅ Назад", callback_data="crypto")]])
        await call.message.edit_text(text, reply_markup=kb, parse_mode="HTML")

# --- PAYMENT SUCCESS ---

@router.pre_checkout_query()
async def pre_checkout(pre: PreCheckoutQuery):
    await pre.answer(ok=True)

@router.message(F.successful_payment)
async def success(message: Message):
    plan_id = message.successful_payment.invoice_payload.split("_")[1]
    days = PLANS[plan_id]["days"]
    ref_id = activate_subscription(message.from_user.id, days)
    if ref_id:
        activate_subscription(ref_id, 7)
        try: await bot.send_message(ref_id, "🎉 Ваш друг оплатил подписку! Вам начислено +7 дней.")
        except: pass
    invite = await bot.create_chat_invite_link(chat_id=CHANNEL_ID, member_limit=1)
    await message.answer(f"✅ Оплата прошла! Ваша ссылка для входа:\n{invite.invite_link}")

# --- REFERRAL & INFO ---

@router.callback_query(F.data == "ref")
async def ref(call: CallbackQuery):
    bot_info = await bot.get_me()
    text = (f"<b>👥 ПРИГЛАСИ ДРУГА — ПОЛУЧИ +7 ДНЕЙ!</b>\n\n"
            f"Как это работает:\n1. Отправь ссылку другу.\n2. При оплате он получит доступ, а ты +7 дней!\n\n"
            f"<b>Твоя ссылка:</b>\n<code>https://t.me/{bot_info.username}?start={call.from_user.id}</code>")
    await call.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⬅ Назад", callback_data="back")]]), parse_mode="HTML")

@router.callback_query(F.data == "info")
async def info(call: CallbackQuery):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📄 Политика конфиденциальности", callback_data="privacy")],
        [InlineKeyboardButton(text="📜 Пользовательское соглашение", callback_data="terms")],
        [InlineKeyboardButton(text="⬅ Назад", callback_data="back")]
    ])
    await call.message.edit_text("ℹ️ Информация", reply_markup=kb)

@router.callback_query(F.data == "privacy")
async def privacy(call: CallbackQuery):
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⬅ Назад", callback_data="info")]])
    await call.message.edit_text(PRIVACY_TEXT, reply_markup=kb)

@router.callback_query(F.data == "terms")
async def terms(call: CallbackQuery):
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⬅ Назад", callback_data="info")]])
    await call.message.edit_text(TERMS_TEXT, reply_markup=kb)

async def main():
    init_db()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
