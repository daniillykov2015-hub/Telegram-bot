import asyncio
import logging
import os
import aiohttp
import aiosqlite

from datetime import datetime, timedelta, timezone

from aiogram import Bot, Dispatcher, Router, F
from aiogram.filters import CommandStart
from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    LabeledPrice,
    ChatJoinRequest,
    PreCheckoutQuery,
)
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.client.default import DefaultBotProperties
from aiogram.exceptions import TelegramBadRequest

# ================== CONFIG ==================
logging.basicConfig(level=logging.INFO)

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CRYPTO_TOKEN = os.getenv("CRYPTO_TOKEN")
CHANNEL_ID = os.getenv("TELEGRAM_GROUP_ID")

# Названия переменных точно как на твоем скриншоте
PAYMENT_TOKEN = os.getenv("PLATEGA_API_KEY") 
MERCHANT_ID = os.getenv("PLATEGA_MERCHANT_ID")

if not BOT_TOKEN or not CRYPTO_TOKEN or not CHANNEL_ID:
    raise ValueError("Missing environment variables!")

CHANNEL_ID = int(CHANNEL_ID)
DB_NAME = "users.db"

bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
dp = Dispatcher(storage=MemoryStorage())
router = Router()
dp.include_router(router)

http_session = None
# ================== TEXTS ==================
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

# ================== ТАРИФЫ (НОВЫЕ ЦЕНЫ) ==================
PLANS = {
    "1": {
        "name": "1 день", 
        "days": 1,
        "rub": 690,    
        "stars": 790,  
        "crypto": 9    
    },
    "7": {
        "name": "7 дней", 
        "days": 7,
        "rub": 1690, 
        "stars": 1790, 
        "crypto": 22
    },
    "30": {
        "name": "30 дней", 
        "days": 30,
        "rub": 3390, 
        "stars": 3490, 
        "crypto": 46
    },
}
# ================== DB LOGIC ==================
async def init_db():
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            expiry TEXT,
            referrer INTEGER,
            ref_count INTEGER DEFAULT 0,
            bonus_days INTEGER DEFAULT 0
        )""")
        await db.execute("""
        CREATE TABLE IF NOT EXISTS crypto_invoices (
            invoice_id TEXT PRIMARY KEY,
            user_id INTEGER,
            plan_id TEXT,
            status TEXT DEFAULT 'pending'
        )""")
        await db.commit()

async def get_user(user_id):
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("SELECT user_id, expiry, referrer, ref_count, bonus_days FROM users WHERE user_id=?", (user_id,)) as cur:
            return await cur.fetchone()

async def extend_user(user_id, days, is_bonus=False):
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("SELECT expiry, referrer FROM users WHERE user_id=?", (user_id,)) as cur:
            row = await cur.fetchone()
        
        if row and row[0]:
            current = datetime.fromisoformat(row[0]).replace(tzinfo=timezone.utc)
            base = max(datetime.now(timezone.utc), current)
        else:
            base = datetime.now(timezone.utc)

        new_expiry = base + timedelta(days=days)
        await db.execute("""
        INSERT INTO users (user_id, expiry) VALUES (?, ?)
        ON CONFLICT(user_id) DO UPDATE SET expiry=excluded.expiry
        """, (user_id, new_expiry.isoformat()))
        
        # Если это обычная покупка (не бонус) и у пользователя есть пригласитель
        if not is_bonus and row and row[1]:
            ref_id = row[1]
            # Проверяем, есть ли у пригласителя активная подписка (условие начисления бонуса)
            async with db.execute("SELECT expiry FROM users WHERE user_id=?", (ref_id,)) as cur:
                ref_row = await cur.fetchone()
                if ref_row and ref_row[0]:
                    ref_expiry = datetime.fromisoformat(ref_row[0]).replace(tzinfo=timezone.utc)
                    if ref_expiry > datetime.now(timezone.utc):
                        # Начисляем 7 дней пригласителю
                        await db.execute("""
                            UPDATE users 
                            SET ref_count = ref_count + 1, 
                                bonus_days = bonus_days + 7 
                            WHERE user_id = ?
                        """, (ref_id,))
                        await db.commit()
                        # Продлеваем срок пригласителю
                        await extend_user(ref_id, 7, is_bonus=True)
                        try:
                            await bot.send_message(ref_id, "💎 <b>Бонус начислен!</b> Ваш друг оплатил подписку, вам добавлено <b>7 дней</b> доступа!")
                        except:
                            pass
        await db.commit()

# ================== KEYBOARDS ==================
def main_menu_kb():
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
    user_id = message.from_user.id
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("INSERT OR IGNORE INTO users (user_id) VALUES (?)", (user_id,))
        if len(args) > 1 and args[1].isdigit():
            referrer = int(args[1])
            # Нельзя пригласить самого себя
            if referrer != user_id:
                await db.execute("UPDATE users SET referrer = ? WHERE user_id = ? AND referrer IS NULL", (referrer, user_id))
        await db.commit()
    await message.answer(MAIN_TEXT, reply_markup=main_menu_kb())

@router.callback_query(F.data == "back")
async def back(call: CallbackQuery):
    await call.message.edit_text(MAIN_TEXT, reply_markup=main_menu_kb())
    await call.answer()

# --- STARS ---
@router.callback_query(F.data == "stars")
async def stars_menu(call: CallbackQuery):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"{p['name']} — {p['stars']} ⭐", callback_data=f"stars_confirm:{k}")]
        for k, p in PLANS.items()
    ] + [[InlineKeyboardButton(text="⬅ Назад", callback_data="back")]])
    await call.message.edit_text("⭐ Выберите период подписки Stars:", reply_markup=kb)
    await call.answer()

@router.callback_query(F.data.startswith("stars_confirm:"))
async def stars_confirm(call: CallbackQuery):
    plan_id = call.data.split(":")[1]
    plan = PLANS[plan_id]
    invoice_link = await bot.create_invoice_link(
        title="Подписка", description=f"Доступ в закрытый канал на {plan['name']}",
        payload=f"stars_{plan_id}", provider_token="", currency="XTR", 
        prices=[LabeledPrice(label="Оплата Stars", amount=plan['stars'])]
    )
    text = (
        "<b>Проверьте детали платежа:</b>\n\n"
        f"📦 Тариф: {plan['name']}\n"
        f"🗓 Срок: {plan['name']}\n"
        "💳 Способ оплаты: ⭐ Telegram Stars\n"
        f"💰 К оплате: {plan['stars']} ⭐\n\n"
        "Нажмите 💸 Оплатить, чтобы перейти к оплате."
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💸 Оплатить", url=invoice_link)],
        [InlineKeyboardButton(text="⬅ Назад", callback_data="stars")]
    ])
    await call.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    await call.answer()

# --- CRYPTO ---
@router.callback_query(F.data == "crypto")
async def crypto_menu(call: CallbackQuery):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"{p['name']} — {p['crypto']}$", callback_data=f"crypto_confirm:{k}")]
        for k, p in PLANS.items()
    ] + [[InlineKeyboardButton(text="⬅ Назад", callback_data="back")]])
    await call.message.edit_text("💰 Выберите тариф Crypto (USDT):", reply_markup=kb)
    await call.answer()

@router.callback_query(F.data.startswith("crypto_confirm:"))
async def crypto_confirm(call: CallbackQuery):
    plan_id = call.data.split(":")[1]
    plan = PLANS[plan_id]
    
    async with http_session.post("https://pay.crypt.bot/api/createInvoice",
        headers={"Crypto-Pay-API-Token": CRYPTO_TOKEN},
        json={"asset": "USDT", "amount": str(plan["crypto"]), "description": f"Subscription {plan['name']}"}
    ) as response:
        r = await response.json()

    if not r.get("ok"):
        await call.message.answer("❌ Ошибка CryptoPay")
        return

    pay_url = r["result"]["pay_url"]
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("INSERT OR IGNORE INTO crypto_invoices (invoice_id, user_id, plan_id) VALUES (?, ?, ?)",
                         (str(r["result"]["invoice_id"]), call.from_user.id, plan_id))
        await db.commit()

    text = (
        "<b>Проверьте детали платежа:</b>\n\n"
        f"📦 Тариф: {plan['name']}\n"
        f"🗓 Срок: {plan['name']}\n"
        "💳 Способ оплаты: 💰 CryptoBot (USDT)\n"
        f"💰 К оплате: {plan['crypto']} $\n\n"
        "Нажмите 💸 Оплатить, чтобы перейти к оплате."
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💸 Оплатить", url=pay_url)],
        [InlineKeyboardButton(text="⬅ Назад", callback_data="crypto")]
    ])
    await call.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    await call.answer()

# --- REFERRAL ---
@router.callback_query(F.data == "ref")
async def ref(call: CallbackQuery):
    user_data = await get_user(call.from_user.id)
    ref_count = user_data[3] if user_data else 0
    bonus_days = user_data[4] if user_data else 0
    
    text = (
        "<b>👥 ПРИГЛАСИ ДРУГА — ПОЛУЧИ +7 ДНЕЙ!</b>\n\n"
        "Хочешь пользоваться закрытым каналом дольше и бесплатно? Участвуй в нашей реферальной программе!\n\n"
        "<b>Как это работает:</b>\n"
        "1. Копируй свою уникальную ссылку ниже.\n"
        "2. Отправь её другу.\n"
        "3. Как только твой друг <b>оплатит любую подписку</b>, тебе автоматически начислится <b>7 дней бесплатного доступа!</b>\n\n"
        "<b>⚠️ Важное условие:</b>\n"
        "Бонус начисляется только в том случае, если на момент приглашения у тебя есть активная подписка.\n\n"
        f"<b>📊 Твоя статистика:</b>\n"
        f"Приглашено друзей: {ref_count}\n"
        f"Получено бонусов: +{bonus_days} дней\n\n"
        "<b>Твоя ссылка для приглашения:</b>\n"
        f"<code>https://t.me/{(await bot.get_me()).username}?start={call.from_user.id}</code>"
    )
    await call.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅ Назад", callback_data="back")]
    ]), parse_mode="HTML")
    await call.answer()

# --- INFO ---
@router.callback_query(F.data == "info")
async def info(call: CallbackQuery):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📄 Политика конфиденциальности", callback_data="privacy")],
        [InlineKeyboardButton(text="📜 Пользовательское соглашение", callback_data="terms")],
        [InlineKeyboardButton(text="⬅ Назад", callback_data="back")]
    ])
    await call.message.edit_text("ℹ️ Информация", reply_markup=kb)
    await call.answer()

@router.callback_query(F.data == "privacy")
async def privacy(call: CallbackQuery):
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⬅ Назад", callback_data="info")]])
    await call.message.edit_text(PRIVACY_TEXT, reply_markup=kb)
    await call.answer()

@router.callback_query(F.data == "terms")
async def terms(call: CallbackQuery):
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⬅ Назад", callback_data="info")]])
    await call.message.edit_text(TERMS_TEXT, reply_markup=kb)
    await call.answer()

# --- PAYMENTS & JOIN ---
@router.pre_checkout_query()
async def pre_checkout(pre: PreCheckoutQuery):
    await pre.answer(ok=True)

@router.message(F.successful_payment)
async def success(message: Message):
    payload = message.successful_payment.invoice_payload
    if payload.startswith("stars_"):
        plan_id = payload.split("_")[1]
        await extend_user(message.from_user.id, PLANS[plan_id]["days"])
        await message.answer("✅ Оплата прошла! Доступ активирован.")

@router.chat_join_request()
async def join(req: ChatJoinRequest):
    user = await get_user(req.from_user.id)
    if user and user[1]:
        if datetime.fromisoformat(user[1]).replace(tzinfo=timezone.utc) > datetime.now(timezone.utc):
            await req.approve()
            return
    await req.decline()

# --- BACKGROUND TASKS ---
async def crypto_checker():
    while True:
        try:
            async with aiosqlite.connect(DB_NAME) as db:
                async with db.execute("SELECT invoice_id, user_id, plan_id FROM crypto_invoices WHERE status='pending'") as cur:
                    invoices = await cur.fetchall()
            
            for inv_id, u_id, p_id in invoices:
                async with http_session.get(f"https://pay.crypt.bot/api/getInvoices?invoice_ids={inv_id}",
                    headers={"Crypto-Pay-API-Token": CRYPTO_TOKEN}) as resp:
                    data = await resp.json()
                
                if data.get("ok") and data["result"]["items"][0]["status"] == "paid":
                    await extend_user(u_id, PLANS[p_id]["days"])
                    async with aiosqlite.connect(DB_NAME) as db:
                        await db.execute("UPDATE crypto_invoices SET status='paid' WHERE invoice_id=?", (inv_id,))
                        await db.commit()
                    try:
                        await bot.send_message(u_id, "✅ Ваша оплата через Crypto принята! Доступ активирован.")
                    except:
                        pass
        except Exception as e:
            logging.error(f"Crypto checker error: {e}")
        await asyncio.sleep(20)

async def check_subscriptions():
    while True:
        try:
            async with aiosqlite.connect(DB_NAME) as db:
                async with db.execute("SELECT user_id, expiry FROM users WHERE expiry IS NOT NULL") as cur:
                    users = await cur.fetchall()

            now = datetime.now(timezone.utc)
            for user_id, expiry_str in users:
                expiry_dt = datetime.fromisoformat(expiry_str).replace(tzinfo=timezone.utc)
                if now > expiry_dt:
                    try:
                        await bot.ban_chat_member(chat_id=CHANNEL_ID, user_id=user_id)
                        await bot.unban_chat_member(chat_id=CHANNEL_ID, user_id=user_id)
                        async with aiosqlite.connect(DB_NAME) as db:
                            await db.execute("UPDATE users SET expiry = NULL WHERE user_id = ?", (user_id,))
                            await db.commit()
                        await bot.send_message(user_id, "❌ Срок вашей подписки истёк. Вы были удалены из канала. Чтобы вернуться, оплатите подписку снова.")
                    except TelegramBadRequest as e:
                        if "user is not found in the chat" not in e.message:
                            logging.error(f"Error banning user {user_id}: {e}")
        except Exception as e:
            logging.error(f"Subscription checker error: {e}")
        await asyncio.sleep(3600)

async def main():
    global http_session
    http_session = aiohttp.ClientSession()
    await init_db()
    
    asyncio.create_task(crypto_checker())
    asyncio.create_task(check_subscriptions())
    
    await dp.start_polling(bot)
    await http_session.close()

if __name__ == "__main__":
    asyncio.run(main())
