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
logger = logging.getLogger(__name__)

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CRYPTO_TOKEN = os.getenv("CRYPTO_TOKEN")
CHANNEL_ID = os.getenv("TELEGRAM_GROUP_ID")

PAYMENT_TOKEN = os.getenv("PLATEGA_API_KEY")
MERCHANT_ID = os.getenv("PLATEGA_MERCHANT_ID")

ADMIN_ID = os.getenv("ADMIN_ID")
if ADMIN_ID:
    try:
        ADMIN_ID = int(ADMIN_ID)
    except ValueError:
        ADMIN_ID = None

missing = []

if not BOT_TOKEN:
    missing.append("TELEGRAM_BOT_TOKEN")

if not CRYPTO_TOKEN:
    missing.append("CRYPTO_TOKEN")

if not CHANNEL_ID:
    missing.append("TELEGRAM_GROUP_ID")

if missing:
    raise ValueError(f"Missing env vars: {', '.join(missing)}")

# ⚠️ безопаснее: не ломаемся если не число
try:
    CHANNEL_ID = int(CHANNEL_ID)
except ValueError:
    pass

DB_NAME = "users.db"

bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
dp = Dispatcher(storage=MemoryStorage())
router = Router()
dp.include_router(router)

http_session = None
tasks = []

# ================== ADMIN NOTIFY ==================
async def notify_admin(user_id: int, plan_name: str, method: str, extra: str = ""):
    if not ADMIN_ID:
        return

    try:
        user = await bot.get_chat(user_id)
        username = f"@{user.username}" if user.username else "нет username"

        text = (
            "💰 <b>НОВАЯ ОПЛАТА</b>\n\n"
            f"👤 Пользователь: {username}\n"
            f"🆔 ID: <code>{user_id}</code>\n"
            f"📦 Тариф: {plan_name}\n"
            f"💳 Способ: {method}\n"
        )

        if extra:
            text += f"\n{extra}"

        await bot.send_message(ADMIN_ID, text)

    except Exception as e:
        logging.error(f"notify_admin error: {e}")
# ================== TEXTS ==================оплаты 👇"
TEXTS = {
    "ru": {
        "main": "👋 Привет, я Ева и это мой закрытый канал\n\n"
                "❓ Что внутри?\n\n"
                "Закрытый контент по подписке\n"
                "💎 Без ограничений\n"
                "🔥 Обновления регулярно\n\n"
                "Выбери способ оплаты 👇"
    },
    "en": {
        "main": "👋 Hi, I'm Eva and this is my private channel\n\n"
                "❓ What's inside?\n\n"
                "Premium content\n"
                "💎 No limits\n"
                "🔥 Regular updates\n\n"
                "Choose payment method 👇"
    },
    "de": {
        "main": "👋 Hallo, ich bin Eva und das ist mein privater Kanal\n\n"
                "❓ Inhalt?\n\n"
                "Premium Inhalte\n"
                "💎 Keine Limits\n"
                "🔥 Updates\n\n"
                "Zahlung wählen 👇"
    },
    "es": {
        "main": "👋 Hola, soy Eva...\n\n"
                "Contenido premium\n"
                "💎 Sin límites\n"
                "🔥 Actualizaciones\n\n"
                "Elige pago 👇"
    },
    "fr": {
        "main": "👋 Salut, je suis Eva...\n\n"
                "Contenu premium\n"
                "💎 Sans limites\n"
                "🔥 Mises à jour\n\n"
                "Choisir paiement 👇"
    }
}

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
            bonus_days INTEGER DEFAULT 0,
            pending_days INTEGER,
            in_chat INTEGER DEFAULT 0,
            lang TEXT DEFAULT 'ru'
        )
        """)

        # ⚠️ ALTER TABLE может падать, если колонка уже есть — это нормально
        try:
            await db.execute("ALTER TABLE users ADD COLUMN lang TEXT DEFAULT 'ru'")
        except:
            pass

        await db.commit()

        # 💰 CRYPTO
        await db.execute("""
        CREATE TABLE IF NOT EXISTS crypto_invoices (
            invoice_id TEXT PRIMARY KEY,
            user_id INTEGER,
            plan_id TEXT,
            status TEXT DEFAULT 'pending'
        )
        """)

        # 💳 CARD / SBP (Platega)
        await db.execute("""
        CREATE TABLE IF NOT EXISTS card_invoices (
            payload TEXT PRIMARY KEY,
            user_id INTEGER,
            plan_id TEXT,
            status TEXT DEFAULT 'pending'
        )
        """)

        # 📎 invite links
        await db.execute("""
        CREATE TABLE IF NOT EXISTS invite_links (
            user_id INTEGER PRIMARY KEY,
            invite_link TEXT,
            expire_at TEXT
        )
        """)

        await db.commit()


async def get_user(user_id):
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute(
            "SELECT user_id, expiry, referrer, ref_count, bonus_days FROM users WHERE user_id=?",
            (user_id,)
        ) as cur:
            return await cur.fetchone()


async def extend_user(user_id, days, is_bonus=False):
    async with aiosqlite.connect(DB_NAME) as db:

        async with db.execute(
            "SELECT expiry, referrer FROM users WHERE user_id=?",
            (user_id,)
        ) as cur:
            row = await cur.fetchone()

        # 📅 база времени
        if row and row[0]:
            current = datetime.fromisoformat(row[0]).replace(tzinfo=timezone.utc)
            base = max(datetime.now(timezone.utc), current)
        else:
            base = datetime.now(timezone.utc)

        new_expiry = base + timedelta(days=days)

        await db.execute("""
            INSERT INTO users (user_id, expiry)
            VALUES (?, ?)
            ON CONFLICT(user_id)
            DO UPDATE SET expiry=excluded.expiry
        """, (user_id, new_expiry.isoformat()))

        # 🎁 рефералка
        if not is_bonus and row and row[1]:

            ref_id = row[1]

            async with db.execute(
                "SELECT expiry FROM users WHERE user_id=?",
                (ref_id,)
            ) as cur:
                ref_row = await cur.fetchone()

            if ref_row and ref_row[0]:

                ref_expiry = datetime.fromisoformat(ref_row[0]).replace(tzinfo=timezone.utc)

                if ref_expiry > datetime.now(timezone.utc):

                    await db.execute("""
                        UPDATE users
                        SET ref_count = ref_count + 1,
                            bonus_days = bonus_days + 7
                        WHERE user_id = ?
                    """, (ref_id,))

                    await db.commit()

                    await extend_user(ref_id, 7, is_bonus=True)

                    try:
                        await bot.send_message(
                            ref_id,
                            "💎 <b>Бонус начислен!</b>\n\n"
                            "Друг оплатил подписку — тебе +7 дней 🔥"
                        )
                    except:
                        pass

        await db.commit()


async def get_lang(user_id):
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute(
            "SELECT lang FROM users WHERE user_id=?",
            (user_id,)
        ) as cur:
            row = await cur.fetchone()
            return row[0] if row and row[0] else "en"

# ================== KEYBOARDS ==================
def lang_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🇷🇺 Русский", callback_data="lang_ru"),
            InlineKeyboardButton(text="🇬🇧 English", callback_data="lang_en"),
        ],
        [
            InlineKeyboardButton(text="🇩🇪 Deutsch", callback_data="lang_de"),
            InlineKeyboardButton(text="🇪🇸 Español", callback_data="lang_es"),
        ],
        [
            InlineKeyboardButton(text="🇫🇷 Français", callback_data="lang_fr"),
        ]
    ])


def main_menu_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="💳 Карта / СБП (₽)", callback_data="pay_card"),
        ],
        [
            InlineKeyboardButton(text="⭐ Stars", callback_data="stars"),
            InlineKeyboardButton(text="💰 Crypto ($)", callback_data="crypto"),
        ],
        [
            InlineKeyboardButton(text="👥 Реферальная система", callback_data="ref"),
            InlineKeyboardButton(text="💬 Поддержка", url="https://t.me/mistybibi"),
        ],
        [
            InlineKeyboardButton(text="ℹ️ Информация", callback_data="info")
        ]
    ])


# ================== INVITE SYSTEM ==================
async def get_or_create_invite(user_id: int, days: int):
    async with aiosqlite.connect(DB_NAME) as db:

        async with db.execute(
            "SELECT invite_link, expire_at FROM invite_links WHERE user_id=?",
            (user_id,)
        ) as cur:
            row = await cur.fetchone()

        now = datetime.now(timezone.utc)

        # ⚠️ защита от битого expire_at
        if row and row[0] and row[1]:
            try:
                exp = datetime.fromisoformat(row[1]).replace(tzinfo=timezone.utc)

                if exp > now:
                    return row[0]
            except Exception:
                pass

        # создаём новую ссылку
        expire_time = now + timedelta(days=days)

        invite = await bot.create_chat_invite_link(
            chat_id=CHANNEL_ID,
            member_limit=0,
            expire_date=int(expire_time.timestamp())
        )

        link = invite.invite_link

        await db.execute("""
            INSERT INTO invite_links (user_id, invite_link, expire_at)
            VALUES (?, ?, ?)
            ON CONFLICT(user_id)
            DO UPDATE SET
                invite_link=excluded.invite_link,
                expire_at=excluded.expire_at
        """, (user_id, link, expire_time.isoformat()))

        await db.commit()

        return link
# ================== KEYBOARDS ==================
def lang_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🇷🇺 Русский", callback_data="lang_ru"),
            InlineKeyboardButton(text="🇬🇧 English", callback_data="lang_en"),
        ],
        [
            InlineKeyboardButton(text="🇩🇪 Deutsch", callback_data="lang_de"),
            InlineKeyboardButton(text="🇪🇸 Español", callback_data="lang_es"),
        ],
        [
            InlineKeyboardButton(text="🇫🇷 Français", callback_data="lang_fr"),
        ]
    ])


async def main_menu_kb(user_id: int):
    lang = await get_lang(user_id)
    t = TEXTS[lang]["buttons"]

    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=t["card"], callback_data="pay_card")],
        [
            InlineKeyboardButton(text=t["stars"], callback_data="stars"),
            InlineKeyboardButton(text=t["crypto"], callback_data="crypto"),
        ],
        [
            InlineKeyboardButton(text=t["ref"], callback_data="ref"),
            InlineKeyboardButton(text=t["support"], url="https://t.me/mistybibi"),
        ],
        [InlineKeyboardButton(text=t["info"], callback_data="info")]
    ])


async def get_or_create_invite(user_id: int, days: int):
    async with aiosqlite.connect(DB_NAME) as db:

        async with db.execute(
            "SELECT invite_link, expire_at FROM invite_links WHERE user_id=?",
            (user_id,)
        ) as cur:
            row = await cur.fetchone()

        now = datetime.now(timezone.utc)

        # если есть активная ссылка — используем
        if row:
            link, expire_at = row
            if expire_at:
                exp = datetime.fromisoformat(expire_at)
                if exp > now:
                    return link

        # создаём новую ссылку
        expire_time = now + timedelta(days=days)

        invite = await bot.create_chat_invite_link(
            chat_id=CHANNEL_ID,
            member_limit=0,
            expire_date=int(expire_time.timestamp())
        )

        link = invite.invite_link

        await db.execute("""
            INSERT INTO invite_links (user_id, invite_link, expire_at)
            VALUES (?, ?, ?)
            ON CONFLICT(user_id)
            DO UPDATE SET
                invite_link=excluded.invite_link,
                expire_at=excluded.expire_at
        """, (user_id, link, expire_time.isoformat()))

        await db.commit()

        return link


# ================== HANDLERS ==================

@router.callback_query(F.data.startswith("lang_"))
async def set_lang(call: CallbackQuery):
    user_id = call.from_user.id
    lang = call.data.split("_")[1]

    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute(
            "UPDATE users SET lang=? WHERE user_id=?",
            (lang, user_id)
        )
        await db.commit()

    await call.message.edit_text(
        TEXTS[lang]["main"],
        reply_markup=await main_menu_kb(user_id)
    )
    await call.answer()


# ---------- STARS ----------

@router.callback_query(F.data == "stars")
async def stars_menu(call: CallbackQuery):
    lang = await get_lang(call.from_user.id)
    t = TEXTS[lang]["buttons"]

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text=f"{p['name']} — {p['stars']} ⭐",
                callback_data=f"stars_confirm:{k}"
            )
        ]
        for k, p in PLANS.items()
    ] + [[InlineKeyboardButton(text=t["back"], callback_data="back")]])

    await call.message.edit_text(
        "⭐ Выберите период подписки:",
        reply_markup=kb
    )
    await call.answer()


@router.callback_query(F.data.startswith("stars_confirm:"))
async def stars_confirm(call: CallbackQuery):
    lang = await get_lang(call.from_user.id)
    t = TEXTS[lang]["buttons"]

    plan_id = call.data.split(":")[1]
    plan = PLANS.get(plan_id)

    if not plan:
        await call.answer("Тариф не найден", show_alert=True)
        return

    invoice_link = await bot.create_invoice_link(
        title="Subscription",
        description=f"Access for {plan['name']}",
        payload=f"stars_{plan_id}",
        provider_token="",
        currency="XTR",
        prices=[LabeledPrice(label="Stars", amount=plan["stars"])]
    )

    text = (
        "<b>Проверьте детали платежа:</b>\n\n"
        f"📦 Тариф: {plan['name']}\n"
        f"🗓 Срок: {plan['name']}\n"
        "💳 Способ: ⭐ Stars\n"
        f"💰 К оплате: {plan['stars']} ⭐"
    )

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💸 Оплатить", url=invoice_link)],
        [InlineKeyboardButton(text=t["back"], callback_data="stars")]
    ])

    await call.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    await call.answer()


# ---------- CARD ----------

@router.callback_query(F.data == "pay_card")
async def pay_card(call: CallbackQuery):
    lang = await get_lang(call.from_user.id)
    t = TEXTS[lang]["buttons"]

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text=f"{p['name']} — {p['rub']}₽",
                callback_data=f"card_confirm:{k}"
            )
        ]
        for k, p in PLANS.items()
    ] + [[InlineKeyboardButton(text=t["back"], callback_data="back")]])

    await call.message.edit_text(
        "💳 Выберите тариф:",
        reply_markup=kb
    )
    await call.answer()


# ---------- START ----------

@router.message(CommandStart())
async def start(message: Message):
    user_id = message.from_user.id

    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute(
            "INSERT OR IGNORE INTO users (user_id) VALUES (?)",
            (user_id,)
        )
        await db.commit()

    await message.answer(
        "🌍 Choose your language / Выберите язык:",
        reply_markup=lang_kb()
    )


# ---------- BACK ----------

@router.callback_query(F.data == "back")
async def back(call: CallbackQuery):
    user_id = call.from_user.id
    lang = await get_lang(user_id)

    await call.message.edit_text(
        TEXTS[lang]["main"],
        reply_markup=await main_menu_kb(user_id)
    )
    await call.answer()


# ---------- JOIN TRACK ----------

from aiogram.types import ChatMemberUpdated

@router.chat_member()
async def on_member_update(event: ChatMemberUpdated):
    try:
        user_id = event.from_user.id

        if event.new_chat_member.status in ("member", "administrator"):

            async with aiosqlite.connect(DB_NAME) as db:
                async with db.execute(
                    "SELECT pending_days FROM users WHERE user_id=?",
                    (user_id,)
                ) as cur:
                    row = await cur.fetchone()

            if not row or not row[0]:
                return

            days = row[0]

            await extend_user(user_id, days)

            async with aiosqlite.connect(DB_NAME) as db:
                await db.execute(
                    "UPDATE users SET pending_days=NULL, in_chat=1 WHERE user_id=?",
                    (user_id,)
                )
                await db.commit()

            try:
                await bot.send_message(
                    user_id,
                    f"✅ Доступ активирован!\n\n⏳ {days} дней с момента входа"
                )
            except:
                pass

    except Exception as e:
        logging.error(f"chat_member error: {e}")
# --- PLATEGA ---
@router.callback_query(F.data.startswith("card_confirm:"))
async def card_confirm(call: CallbackQuery):
    plan_id = call.data.split(":")[1]
    plan = PLANS.get(plan_id)

    if not plan:
        await call.answer("❌ Тариф не найден", show_alert=True)
        return

    if http_session is None:
        await call.message.answer("❌ Сервис временно недоступен")
        await call.answer()
        return

    try:
        transaction_id = None
        pay_url = None

        # 1. ищем активный платёж
        async with aiosqlite.connect(DB_NAME) as db:
            async with db.execute(
                """
                SELECT payload 
                FROM card_invoices 
                WHERE user_id=? AND plan_id=? AND status='pending'
                """,
                (call.from_user.id, plan_id)
            ) as cur:
                existing = await cur.fetchone()

        # 2. если есть — проверяем его
        if existing:
            transaction_id = existing[0]

            async with http_session.get(
                f"https://app.platega.io/transaction/{transaction_id}",
                headers={
                    "X-MerchantId": MERCHANT_ID,
                    "X-Secret": PAYMENT_TOKEN
                }
            ) as resp:
                try:
                    data = await resp.json()
                except Exception:
                    data = {}

            pay_url = data.get("redirect")

            # если платёж умер — чистим
            if not pay_url:
                async with aiosqlite.connect(DB_NAME) as db:
                    await db.execute(
                        "UPDATE card_invoices SET status='expired' WHERE payload=?",
                        (transaction_id,)
                    )
                    await db.commit()

                transaction_id = None
                pay_url = None

        # 3. создаём новый платёж
        if not transaction_id:
            payload = {
                "paymentMethod": 2,
                "paymentDetails": {
                    "amount": float(plan["rub"]),
                    "currency": "RUB"
                },
                "description": f"TgId:{call.from_user.id} | User:{call.from_user.id}"
            }

            async with http_session.post(
                "https://app.platega.io/transaction/process",
                headers={
                    "X-MerchantId": MERCHANT_ID,
                    "X-Secret": PAYMENT_TOKEN,
                    "Content-Type": "application/json"
                },
                json=payload
            ) as resp:

                raw_text = await resp.text()

                try:
                    data = await resp.json()
                except Exception:
                    await call.message.answer("❌ Ошибка платежного сервиса")
                    return

            transaction_id = data.get("transactionId")
            pay_url = data.get("redirect")

            if not transaction_id or not pay_url:
                await call.message.answer(f"❌ Ошибка Platega:\n{raw_text}")
                return

            # сохраняем
            async with aiosqlite.connect(DB_NAME) as db:
                await db.execute(
                    """
                    INSERT INTO card_invoices (payload, user_id, plan_id, status)
                    VALUES (?, ?, ?, ?)
                    """,
                    (transaction_id, call.from_user.id, plan_id, "pending")
                )
                await db.commit()

        # 4. UX
        await call.answer("⏳ Создаём платёж...", show_alert=False)

        await call.message.edit_reply_markup(reply_markup=None)

        await call.message.edit_text(
            "⏳ <b>Готовим платёж...</b>\n\nПодождите пару секунд",
            parse_mode="HTML"
        )

        await call.message.edit_text(
            f"💳 <b>Оплата {plan['name']}</b>\n\n"
            f"💰 Сумма: <b>{plan['rub']} ₽</b>\n\n"
            "👇 Нажмите кнопку ниже для оплаты",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="💸 Оплатить", url=pay_url)],
                [InlineKeyboardButton(text="⬅ Назад", callback_data="pay_card")]
            ]),
            parse_mode="HTML"
        )

    except Exception as e:
        logger.exception(f"PLATEGA ERROR: {e}")
        await call.message.answer("❌ Ошибка создания платежа")

    await call.answer()
# --- CRYPTO ---
@router.callback_query(F.data.startswith("crypto_confirm:"))
async def crypto_confirm(call: CallbackQuery):
    plan_id = call.data.split(":")[1]
    plan = PLANS.get(plan_id)

    if not plan:
        await call.answer("❌ Тариф не найден", show_alert=True)
        return

    if http_session is None:
        await call.message.answer("❌ Сервис временно недоступен")
        await call.answer()
        return

    try:
        async with http_session.post(
            "https://pay.crypt.bot/api/createInvoice",
            headers={"Crypto-Pay-API-Token": CRYPTO_TOKEN},
            json={
                "asset": "USDT",
                "amount": float(plan["crypto"]),
                "description": f"Subscription {plan['name']}"
            }
        ) as response:

            # CryptoBot иногда отдаёт 201
            if response.status not in (200, 201):
                text = await response.text()
                logger.error(f"Crypto HTTP error: {response.status} | {text}")
                await call.message.answer("❌ Ошибка соединения с CryptoBot")
                return

            try:
                data = await response.json()
            except Exception:
                text = await response.text()
                logger.error(f"Crypto invalid JSON: {text}")
                await call.message.answer("❌ Ошибка ответа CryptoBot")
                return

        # ❗ проверка ответа API
        if not data.get("ok"):
            logger.error(f"Crypto API error: {data}")
            await call.message.answer("❌ Ошибка оплаты. Попробуйте позже")
            return

        result = data["result"]

        pay_url = result.get("pay_url")
        invoice_id = str(result.get("invoice_id"))

        if not pay_url or not invoice_id:
            await call.message.answer("❌ Некорректный инвойс CryptoBot")
            return

        # 💾 сохраняем
        async with aiosqlite.connect(DB_NAME) as db:
            await db.execute(
                """
                INSERT OR IGNORE INTO crypto_invoices (invoice_id, user_id, plan_id)
                VALUES (?, ?, ?)
                """,
                (invoice_id, call.from_user.id, plan_id)
            )
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

    except Exception as e:
        logger.error(f"Crypto createInvoice error: {e}")
        await call.message.answer("❌ Ошибка создания платежа")

    await call.answer()

# --- REFERRAL ---
@router.callback_query(F.data == "ref")
async def ref(call: CallbackQuery):
    user_data = await get_user(call.from_user.id)

    ref_count = user_data[3] if user_data and user_data[3] else 0
    bonus_days = user_data[4] if user_data and user_data[4] else 0

    bot_username = (await bot.get_me()).username
    ref_link = f"https://t.me/{bot_username}?start={call.from_user.id}"

    text = (
        "<b>👥 ПРИГЛАСИ ДРУГА — ПОЛУЧИ +7 ДНЕЙ!</b>\n\n"
        "Хочешь пользоваться закрытым каналом дольше и бесплатно? Участвуй в нашей реферальной программе!\n\n"
        "<b>Как это работает:</b>\n"
        "1. Копируй свою ссылку.\n"
        "2. Отправь её другу.\n"
        "3. Как только друг <b>оплатит подписку</b>, тебе начислится <b>+7 дней</b>.\n\n"
        "<b>⚠️ Условие:</b>\n"
        "Бонус начисляется только при активной подписке.\n\n"
        f"<b>📊 Твоя статистика:</b>\n"
        f"Приглашено друзей: {ref_count}\n"
        f"Получено бонусов: +{bonus_days} дней\n\n"
        "<b>Твоя ссылка:</b>\n"
        f"<code>{ref_link}</code>"
    )

    await call.message.edit_text(
        text,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⬅ Назад", callback_data="back")]
        ]),
        parse_mode="HTML"
    )

    await call.answer()

# --- INFO ---

@router.callback_query(F.data == "info")
async def info(call: CallbackQuery):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📄 Политика конфиденциальности", callback_data="privacy")],
        [InlineKeyboardButton(text="📜 Пользовательское соглашение", callback_data="terms")],
        [InlineKeyboardButton(text="⬅ Назад", callback_data="back")]
    ])

    try:
        await call.message.edit_text("ℹ️ Информация", reply_markup=kb)
    except TelegramBadRequest:
        pass

    await call.answer()


@router.callback_query(F.data == "privacy")
async def privacy(call: CallbackQuery):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅ Назад", callback_data="info")]
    ])

    try:
        await call.message.edit_text(PRIVACY_TEXT, reply_markup=kb)
    except TelegramBadRequest:
        pass

    await call.answer()


@router.callback_query(F.data == "terms")
async def terms(call: CallbackQuery):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅ Назад", callback_data="info")]
    ])

    try:
        await call.message.edit_text(TERMS_TEXT, reply_markup=kb)
    except TelegramBadRequest:
        pass

    await call.answer()

# --- PAYMENTS & JOIN ---

# лучше тянуть из env (гибкость)
JOIN_LINK = os.getenv("JOIN_LINK", "https://t.me/+ffk7dB_5zPhkMWFk")

@router.pre_checkout_query()
async def pre_checkout(pre: PreCheckoutQuery):
    await pre.answer(ok=True)


@router.message(F.successful_payment)
async def success(message: Message):
    try:
        payment = message.successful_payment
        payload = payment.invoice_payload

        # 🔒 защита от мусорных payload
        if not payload or "_" not in payload:
            return

        # ⭐ Stars only
        if not payload.startswith("stars_"):
            return

        plan_id = payload.split("_", 1)[1]
        plan = PLANS.get(plan_id)

        if not plan:
            await message.answer("❌ Тариф не найден")
            return

        user_id = message.from_user.id
        days = plan["days"]

        # 🎯 начисление подписки
        await extend_user(user_id, days)

        # 🔔 уведомление админу
        if ADMIN_ID:
            try:
                await notify_admin(
                    user_id=user_id,
                    plan_name=plan["name"],
                    method="Stars ⭐",
                    extra=f"💳 Payment ID: {payment.provider_payment_charge_id}"
                )
            except Exception as admin_err:
                logging.error(f"Admin notification error: {admin_err}")

        # 🔥 кнопка входа
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(
                text="📢 Вступить в закрытый канал",
                url=JOIN_LINK
            )]
        ])

        await message.answer(
            (
                "✅ Оплата прошла успешно!\n\n"
                f"🎉 Доступ активирован на <b>{days} дн.</b>\n\n"
                "👇 Нажмите кнопку ниже и отправьте заявку на вступление\n"
                "👤 После этого администратор подтвердит доступ"
            ),
            reply_markup=kb,
            parse_mode="HTML"
        )

    except Exception as e:
        logging.error(f"Stars success error: {e}")
        await message.answer(
            "❌ Ошибка обработки оплаты. Напишите в поддержку.",
            parse_mode="HTML"
        )

# --- BACKGROUND TASKS ---

JOIN_LINK = "https://t.me/+ffk7dB_5zPhkMWFk"

async def card_checker():
    while True:
        try:
            async with aiosqlite.connect(DB_NAME) as db:
                async with db.execute(
                    "SELECT payload, user_id, plan_id FROM card_invoices WHERE status='pending'"
                ) as cur:
                    invoices = await cur.fetchall()

            for transaction_id, user_id, plan_id in invoices:
                try:
                    async with http_session.get(
                        f"https://app.platega.io/transaction/{transaction_id}",
                        headers={
                            "X-MerchantId": MERCHANT_ID,
                            "X-Secret": PAYMENT_TOKEN
                        }
                    ) as resp:

                        if resp.status != 200:
                            continue

                        data = await resp.json()

                    status = str(data.get("status", "")).upper()

                    # ⛔ ждём оплату
                    if status not in ("CONFIRMED", "SUCCESS", "PAID"):
                        continue

                    # 🔒 атомарно помечаем как оплачено (чтобы не задвоило выдачу)
                    async with aiosqlite.connect(DB_NAME) as db:
                        cursor = await db.execute(
                            """
                            UPDATE card_invoices
                            SET status='paid'
                            WHERE payload=? AND status='pending'
                            """,
                            (transaction_id,)
                        )
                        await db.commit()

                    # ⚠️ важно: проверка должна быть ДО commit логики
                    if cursor.rowcount == 0:
                        continue

                    days = PLANS[plan_id]["days"]

                    # 🎯 начисляем подписку
                    await extend_user(user_id, days)

                    # 🔔 УВЕДОМЛЕНИЕ АДМИНУ
                    if ADMIN_ID:
                        try:
                            await notify_admin(
                                user_id=user_id,
                                plan_name=PLANS[plan_id]["name"],
                                method="Card / SBP 💳",
                                extra=f"🔗 Tx: <code>{transaction_id}</code>"
                            )
                        except Exception as admin_err:
                            logger.error(f"Admin notification error (Card): {admin_err}")

                    # 🔥 выдаём доступ
                    kb = InlineKeyboardMarkup(inline_keyboard=[
                        [InlineKeyboardButton(
                            text="📢 Вступить в закрытый канал",
                            url=JOIN_LINK
                        )]
                    ])

                    await bot.send_message(
                        user_id,
                        (
                            "✅ Оплата прошла успешно!\n\n"
                            f"🎉 Доступ активирован на <b>{days} дн.</b>\n\n"
                            "👇 Нажмите кнопку и отправьте заявку на вступление\n"
                            "👤 После этого администратор подтвердит доступ"
                        ),
                        reply_markup=kb,
                        parse_mode="HTML"
                    )

                except Exception as e:
                    logger.error(f"Card inner error: {e}")

        except Exception as e:
            logger.error(f"Card checker loop error: {e}")

        await asyncio.sleep(5)
# --- КРИПТО-ЧЕКЕР (CryptoBot) ---

async def crypto_checker():
    while True:
        try:
            async with aiosqlite.connect(DB_NAME) as db:
                async with db.execute(
                    "SELECT invoice_id, user_id, plan_id FROM crypto_invoices WHERE status='pending'"
                ) as cur:
                    invoices = await cur.fetchall()

            for inv_id, user_id, plan_id in invoices:
                try:
                    async with http_session.get(
                        "https://pay.crypt.bot/api/getInvoices",
                        headers={"Crypto-Pay-API-Token": CRYPTO_TOKEN},
                        params={"invoice_ids": inv_id}
                    ) as resp:

                        if resp.status != 200:
                            logger.error(f"Crypto HTTP error: {resp.status}")
                            continue

                        data = await resp.json()

                    if not data.get("ok"):
                        logger.error(f"Crypto API error: {data}")
                        continue

                    items = data.get("result", {}).get("items", [])
                    if not items:
                        continue

                    item = items[0]
                    status = str(item.get("status", "")).lower()

                    # ⛔ строго ждём paid
                    if status != "paid":
                        continue

                    # 🔒 атомарное обновление (защита от дубля)
                    async with aiosqlite.connect(DB_NAME) as db:
                        cursor = await db.execute(
                            """
                            UPDATE crypto_invoices
                            SET status='paid'
                            WHERE invoice_id=? AND status='pending'
                            """,
                            (inv_id,)
                        )
                        await db.commit()

                    if cursor.rowcount == 0:
                        continue

                    days = PLANS[plan_id]["days"]

                    # 🎯 начисляем подписку
                    await extend_user(user_id, days)

                    # 🔔 уведомление админу
                    if ADMIN_ID:
                        try:
                            await notify_admin(
                                user_id=user_id,
                                plan_name=PLANS[plan_id]["name"],
                                method="Crypto 💰",
                                extra=f"🆔 Invoice: <code>{inv_id}</code>"
                            )
                        except Exception as e:
                            logger.error(f"Admin notify error: {e}")

                    # 🔥 выдача доступа
                    kb = InlineKeyboardMarkup(inline_keyboard=[
                        [InlineKeyboardButton(
                            text="📢 Вступить в закрытый канал",
                            url=JOIN_LINK
                        )]
                    ])

                    await bot.send_message(
                        user_id,
                        (
                            "✅ Оплата через Crypto подтверждена!\n\n"
                            f"🎉 Доступ активирован на <b>{days} дн.</b>\n\n"
                            "👇 Нажмите кнопку и отправьте заявку на вступление\n"
                            "👤 После этого администратор подтвердит доступ"
                        ),
                        reply_markup=kb,
                        parse_mode="HTML"
                    )

                except Exception as e:
                    logger.error(f"Crypto inner error: {e}")

        except Exception as e:
            logger.error(f"Crypto checker loop error: {e}")

        await asyncio.sleep(15)

async def check_subscriptions():
    while True:
        try:
            async with aiosqlite.connect(DB_NAME) as db:
                async with db.execute(
                    "SELECT user_id, expiry FROM users WHERE expiry IS NOT NULL"
                ) as cur:
                    users = await cur.fetchall()

            now = datetime.now(timezone.utc)

            for user_id, expiry_str in users:
                try:
                    if not expiry_str:
                        continue

                    expiry_dt = datetime.fromisoformat(expiry_str).replace(tzinfo=timezone.utc)

                    # ⛔ ещё активен — пропускаем
                    if now <= expiry_dt:
                        continue

                    # 🚫 удаляем из канала
                    try:
                        await bot.ban_chat_member(chat_id=CHANNEL_ID, user_id=user_id)
                        await bot.unban_chat_member(chat_id=CHANNEL_ID, user_id=user_id)
                    except TelegramBadRequest as e:
                        # если пользователя уже нет в чате — просто игнор
                        if "user is not found in the chat" not in str(e):
                            logging.error(f"Error banning user {user_id}: {e}")

                    # 🧹 чистим подписку
                    async with aiosqlite.connect(DB_NAME) as db:
                        await db.execute(
                            "UPDATE users SET expiry = NULL WHERE user_id = ?",
                            (user_id,)
                        )
                        await db.commit()

                    # 📩 уведомление пользователю
                    try:
                        await bot.send_message(
                            user_id,
                            "❌ Срок вашей подписки истёк.\n\n"
                            "Вы были удалены из канала.\n"
                            "Чтобы вернуться — просто оплатите подписку снова."
                        )
                    except Exception as e:
                        logging.error(f"Notify user error {user_id}: {e}")

                except Exception as e:
                    logging.error(f"User expiry check error {user_id}: {e}")

        except Exception as e:
            logging.error(f"Subscription checker error: {e}")

        await asyncio.sleep(1200)
      
        
        
async def main():
    global http_session

    http_session = aiohttp.ClientSession()
    await init_db()

    loop = asyncio.get_running_loop()

    # 🧠 фоновые задачи
    tasks.append(loop.create_task(crypto_checker()))
    tasks.append(loop.create_task(card_checker()))
    tasks.append(loop.create_task(check_subscriptions()))

    try:
        await dp.start_polling(bot)

    finally:
        # 🔥 мягкая остановка задач
        for task in tasks:
            task.cancel()

        # ⛑ ждём корректного завершения всех задач
        await asyncio.gather(*tasks, return_exceptions=True)

        # 🌐 закрытие HTTP клиента
        if http_session and not http_session.closed:
            await http_session.close()

        # 🤖 закрытие бота (важно для aiogram стабильности)
        await bot.session.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
