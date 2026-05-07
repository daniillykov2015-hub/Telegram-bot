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
    PreCheckoutQuery,
    ChatMemberUpdated,
)
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.client.default import DefaultBotProperties
from aiogram.exceptions import TelegramBadRequest

# ================== CONFIG ==================
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- ENV ---
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CRYPTO_TOKEN = os.getenv("CRYPTO_TOKEN")
CHANNEL_ID = os.getenv("TELEGRAM_GROUP_ID")

PAYMENT_TOKEN = os.getenv("PLATEGA_API_KEY")
MERCHANT_ID = os.getenv("PLATEGA_MERCHANT_ID")

ADMIN_ID = os.getenv("ADMIN_ID")

# --- SAFE VALIDATION (FIX CRASHES) ---
required_vars = {
    "TELEGRAM_BOT_TOKEN": BOT_TOKEN,
    "CRYPTO_TOKEN": CRYPTO_TOKEN,
    "TELEGRAM_GROUP_ID": CHANNEL_ID,
    "PLATEGA_API_KEY": PAYMENT_TOKEN,
    "PLATEGA_MERCHANT_ID": MERCHANT_ID,
}

missing = [k for k, v in required_vars.items() if not v]
if missing:
    raise RuntimeError(f"Missing env vars: {', '.join(missing)}")

# --- SAFE CONVERSIONS ---
CHANNEL_ID = int(CHANNEL_ID)

ADMIN_ID = int(ADMIN_ID) if ADMIN_ID and str(ADMIN_ID).isdigit() else None

# --- DB ---
DB_NAME = "users.db"

# --- BOT ---
bot = Bot(
    token=BOT_TOKEN,
    default=DefaultBotProperties(parse_mode="HTML")
)

dp = Dispatcher(storage=MemoryStorage())
router = Router()
dp.include_router(router)

# --- GLOBALS ---
http_session: aiohttp.ClientSession | None = None
tasks: list[asyncio.Task] = []
# ================== TEXTS ==================
TEXTS = {
    "ru": {
        "main": (
            "👋 Привет, я Ева\n\n"
            "Это мой закрытый канал 🔥\n\n"
            "📌 Эксклюзивный контент\n"
            "💎 Полный доступ\n"
            "🔄 Регулярные обновления\n\n"
            "Хочешь получить доступ? 👇"
        )
    },

    "en": {
        "main": (
            "👋 Hey, I’m Eva\n\n"
            "This is my private channel 🔥\n\n"
            "📌 Exclusive content\n"
            "💎 Full access\n"
            "🔄 Regular updates\n\n"
            "Want to get access? 👇"
        )
    },

    "es": {
        "main": (
            "👋 Hola, soy Eva\n\n"
            "Este es mi canal privado 🔥\n\n"
            "📌 Contenido exclusivo\n"
            "💎 Acceso completo\n"
            "🔄 Actualizaciones frecuentes\n\n"
            "¿Quieres acceder? 👇"
        )
    },

    "de": {
        "main": (
            "👋 Hey, ich bin Eva\n\n"
            "Das ist mein privater Kanal 🔥\n\n"
            "📌 Exklusive Inhalte\n"
            "💎 Voller Zugang\n"
            "🔄 Regelmäßige Updates\n\n"
            "Willst du Zugang? 👇"
        )
    },

    "fr": {
        "main": (
            "👋 Salut, moi c’est Eva\n\n"
            "C’est mon canal privé 🔥\n\n"
            "📌 Contenu exclusif\n"
            "💎 Accès complet\n"
            "🔄 Mises à jour régulières\n\n"
            "Tu veux accéder ? 👇"
        )
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
async def upsert_user(user_id: int, language: str, referrer: int | None = None):
    async with aiosqlite.connect(DB_NAME) as db:

        await db.execute("""
        INSERT INTO users (user_id, language, referrer)
        VALUES (?, ?, ?)
        ON CONFLICT(user_id)
        DO UPDATE SET
            language = excluded.language,
            referrer = COALESCE(users.referrer, excluded.referrer)
        """, (user_id, language, referrer))

        await db.commit()

async def init_db():
    async with aiosqlite.connect(DB_NAME) as db:

        # 👤 USERS
        await db.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            expiry TEXT,
            referrer INTEGER,
            ref_count INTEGER DEFAULT 0,
            bonus_days INTEGER DEFAULT 0,
            pending_days INTEGER,
            in_chat INTEGER DEFAULT 0,
            language TEXT DEFAULT 'en'
        )
        """)

        # 💰 CRYPTO
        await db.execute("""
        CREATE TABLE IF NOT EXISTS crypto_invoices (
            invoice_id TEXT PRIMARY KEY,
            user_id INTEGER,
            plan_id TEXT,
            status TEXT DEFAULT 'pending'
        )
        """)

        # 💳 CARD / SBP
        await db.execute("""
        CREATE TABLE IF NOT EXISTS card_invoices (
            payload TEXT PRIMARY KEY,
            user_id INTEGER,
            plan_id TEXT,
            status TEXT DEFAULT 'pending'
        )
        """)

        # 🔗 INVITE LINKS
        await db.execute("""
        CREATE TABLE IF NOT EXISTS invite_links (
            user_id INTEGER PRIMARY KEY,
            invite_link TEXT,
            expire_at TEXT
        )
        """)

        await db.commit()


# --- GET USER ---
async def get_user(user_id: int):
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("""
            SELECT user_id, expiry, referrer, ref_count, bonus_days,
                   pending_days, in_chat, language
            FROM users
            WHERE user_id=?
        """, (user_id,)) as cur:
            return await cur.fetchone()


# --- EXTEND SUB ---
async def extend_user(user_id: int, days: int, is_bonus: bool = False):
    async with aiosqlite.connect(DB_NAME) as db:

        async with db.execute(
            "SELECT expiry, referrer FROM users WHERE user_id=?",
            (user_id,)
        ) as cur:
            row = await cur.fetchone()

        # 📅 расчёт времени подписки
        now = datetime.now(timezone.utc)

        if row and row[0]:
            try:
                current = datetime.fromisoformat(row[0])
                if current.tzinfo is None:
                    current = current.replace(tzinfo=timezone.utc)
            except Exception:
                current = now

            base = max(now, current)
        else:
            base = now

        new_expiry = base + timedelta(days=days)

        # ✅ UPSERT пользователя (НЕ теряем другие поля)
        await db.execute("""
        INSERT INTO users (user_id, expiry, in_chat)
        VALUES (?, ?, 1)
        ON CONFLICT(user_id)
        DO UPDATE SET
            expiry=excluded.expiry,
            in_chat=1
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
                try:
                    ref_expiry = datetime.fromisoformat(ref_row[0])
                    if ref_expiry.tzinfo is None:
                        ref_expiry = ref_expiry.replace(tzinfo=timezone.utc)
                except Exception:
                    ref_expiry = now

                if ref_expiry > now:

                    await db.execute("""
                        UPDATE users
                        SET ref_count = ref_count + 1,
                            bonus_days = bonus_days + 7
                        WHERE user_id = ?
                    """, (ref_id,))

                    await db.commit()

                    # 🎁 бонус рефералу
                    await extend_user(ref_id, 7, is_bonus=True)

                    try:
                        await bot.send_message(
                            ref_id,
                            "💎 Бонус начислен!\n\n+7 дней за друга 🔥"
                        )
                    except Exception:
                        pass

        await db.commit()


# --- SET PENDING ---
async def set_pending(user_id: int, days: int):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("""
            INSERT INTO users (user_id, pending_days)
            VALUES (?, ?)
            ON CONFLICT(user_id)
            DO UPDATE SET pending_days=excluded.pending_days
        """, (user_id, days))
        await db.commit()

# ================== KEYBOARDS ==================

# --- тексты кнопок ---
KB_TEXTS = {
    "ru": {
        "card": "💳 Карта / СБП",
        "stars": "⭐ Stars",
        "crypto": "💰 Crypto",
        "ref": "👥 Рефералы",
        "support": "💬 Поддержка",
        "settings": "⚙️ Настройки"
    },
    "en": {
        "card": "💳 Card / SBP",
        "stars": "⭐ Stars",
        "crypto": "💰 Crypto",
        "ref": "👥 Referral",
        "support": "💬 Support",
        "settings": "⚙️ Settings"
    },
    "es": {
        "card": "💳 Tarjeta",
        "stars": "⭐ Stars",
        "crypto": "💰 Crypto",
        "ref": "👥 Referidos",
        "support": "💬 Soporte",
        "settings": "⚙️ Ajustes"
    },
    "de": {
        "card": "💳 Karte",
        "stars": "⭐ Stars",
        "crypto": "💰 Crypto",
        "ref": "👥 Empfehlungen",
        "support": "💬 Support",
        "settings": "⚙️ Einstellungen"
    },
    "fr": {
        "card": "💳 Carte",
        "stars": "⭐ Stars",
        "crypto": "💰 Crypto",
        "ref": "👥 Parrainage",
        "support": "💬 Support",
        "settings": "⚙️ Paramètres"
    }
}



# --- главное меню ---
async def main_menu_kb(user_id: int):
    lang = await get_lang(user_id)
    t = KB_TEXTS.get(lang, KB_TEXTS["en"])

    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text=t["card"], callback_data="pay_card"),
        ],
        [
            InlineKeyboardButton(text=t["stars"], callback_data="stars"),
            InlineKeyboardButton(text=t["crypto"], callback_data="crypto_menu"),
        ],
        [
            InlineKeyboardButton(text=t["ref"], callback_data="ref"),
            InlineKeyboardButton(text=t["support"], url="https://t.me/mistybibi"),
        ],
        [
            InlineKeyboardButton(text=t["settings"], callback_data="settings"),
        ]
    ])


# --- меню выбора языка (с флагами) ---
LANG_KB = InlineKeyboardMarkup(inline_keyboard=[
    [
        InlineKeyboardButton(text="🇷🇺 Русский", callback_data="lang:ru"),
        InlineKeyboardButton(text="🇬🇧 English", callback_data="lang:en"),
    ],
    [
        InlineKeyboardButton(text="🇪🇸 Español", callback_data="lang:es"),
        InlineKeyboardButton(text="🇩🇪 Deutsch", callback_data="lang:de"),
    ],
    [
        InlineKeyboardButton(text="🇫🇷 Français", callback_data="lang:fr"),
    ]
])


# --- получаем язык ---
async def get_lang(user_id: int):
    user = await get_user(user_id)
    # В таблице users столбец language идет 8-м по счету (индекс 7)
    if user and user[7]:
        return user[7]
    return "en"


# ================== INVITE (оставляем, но опционально) ==================

async def get_or_create_invite(user_id: int, days: int):
    async with aiosqlite.connect(DB_NAME) as db:

        async with db.execute(
            "SELECT invite_link, expire_at FROM invite_links WHERE user_id=?",
            (user_id,)
        ) as cur:
            row = await cur.fetchone()

        now = datetime.now(timezone.utc)

        if row:
            link, expire_at = row

            if expire_at:
                exp = datetime.fromisoformat(expire_at)

                if exp > now:
                    return link

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

# --- SETTINGS & INFO HANDLERS ---

@router.callback_query(F.data == "settings")
async def settings_menu(call: CallbackQuery):
    lang = await get_lang(call.from_user.id)
    
    # Тексты кнопок в зависимости от языка
    btns = {
        "ru": {"lang": "🌍 Сменить язык", "info": "📄 О сервисе / Privacy"},
        "en": {"lang": "🌍 Change Language", "info": "📄 About / Privacy"},
        "es": {"lang": "🌍 Cambiar idioma", "info": "📄 Privacidad"},
        "de": {"lang": "🌍 Sprache ändern", "info": "📄 Datenschutz"},
        "fr": {"lang": "🌍 Changer de langue", "info": "📄 Confidentialité"}
    }
    b = btns.get(lang, btns["en"])

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=b["lang"], callback_data="show_lang_menu")],
        [InlineKeyboardButton(text=b["info"], callback_data="show_policy")],
        [InlineKeyboardButton(text="⬅ Back", callback_data="back")]
    ])

    title = {"ru": "⚙️ <b>Настройки</b>", "en": "⚙️ <b>Settings</b>"}
    await call.message.edit_text(title.get(lang, title["en"]), reply_markup=kb, parse_mode="HTML")
    await call.answer()

@router.callback_query(F.data == "show_policy")
async def show_policy(call: CallbackQuery):
    lang = await get_lang(call.from_user.id)
    
    # ТВОИ ТЕКСТЫ ПОЛИТИКИ И ИНФОРМАЦИИ
    policy_map = {
        "ru": "📄 <b>О сервисе</b>\n\nДанный бот предоставляет доступ к закрытому контенту. Оплата является добровольным пожертвованием. Возврат средств не предусмотрен. Ваши данные (ID) используются только для работы подписки.",
        "en": "📄 <b>About & Privacy</b>\n\nThis bot provides access to private content. Payments are voluntary. No refunds. Your ID is used only for subscription management.",
        "es": "📄 <b>Privacidad</b>\n\nLos pagos son voluntarios. No hay reembolsos.",
        "de": "📄 <b>Datenschutz</b>\n\nZahlungen sind freiwillig. Keine Rückerstattung.",
        "fr": "📄 <b>Confidentialité</b>\n\nLes paiements sont volontaires. Pas de remboursement."
    }

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅ Back", callback_data="settings")]
    ])

    await call.message.edit_text(
        policy_map.get(lang, policy_map["en"]), 
        reply_markup=kb, 
        parse_mode="HTML"
    )
    await call.answer()

@router.callback_query(F.data == "show_lang_menu")
async def show_lang_menu_callback(call: CallbackQuery):
    # Просто вызываем твою готовую клавиатуру с флагами
    await call.message.edit_text(
        "🌍 Choose your language / Выберите язык",
        reply_markup=LANG_KB
    )
    await call.answer()


# --- CRYPTO MENU ---
@router.callback_query(F.data == "crypto")
async def crypto_menu(call: CallbackQuery):
    lang = await get_lang(call.from_user.id)

    text_map = {
        "ru": (
            "💰 <b>Оплата Crypto</b>\n\n"
            "После оплаты вы получите доступ к каналу автоматически.\n"
            "👇 Выберите тариф"
        ),
        "en": (
            "💰 <b>Crypto Payment</b>\n\n"
            "After payment you will get access automatically.\n"
            "👇 Choose a plan"
        ),
        "es": (
            "💰 <b>Pago Crypto</b>\n\n"
            "Después del pago obtendrás acceso automáticamente.\n"
            "👇 Elige un plan"
        ),
        "de": (
            "💰 <b>Krypto Zahlung</b>\n\n"
            "Nach der Zahlung erhältst du automatisch Zugang.\n"
            "👇 Wähle einen Tarif"
        ),
        "fr": (
            "💰 <b>Paiement Crypto</b>\n\n"
            "Après paiement, l’accès sera activé automatiquement.\n"
            "👇 Choisissez un plan"
        ),
    }

    # кнопки тарифов
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text=f"{p['name']} — {p['crypto']} USDT",
                                 callback_data=f"crypto_confirm:{k}")
        ]
        for k, p in PLANS.items()
    ])

    kb.inline_keyboard.append([
        InlineKeyboardButton(text="⬅ Back", callback_data="back")
    ])

    await call.message.edit_text(
        text_map.get(lang, text_map["en"]),
        reply_markup=kb,
        parse_mode="HTML"
    )

    await call.answer()

# ================== HANDLERS ==================
# --- ADMIN BROADCAST ---
@router.message(F.text.startswith("/broadcast"), F.from_user.id == ADMIN_ID)
async def start_broadcast(message: Message, bot: Bot):
    # Извлекаем текст сообщения (все, что идет после команды /broadcast)
    broadcast_text = message.text.replace("/broadcast", "").strip()
    
    if not broadcast_text:
        await message.answer("❌ <b>Ошибка:</b> Введите текст после команды.\nПример: <code>/broadcast Привет!</code>")
        return

    # Получаем список всех ID пользователей из базы данных
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("SELECT user_id FROM users") as cursor:
            users = await cursor.fetchall()
    
    count = 0
    # Отправляем сообщение каждому пользователю
    for (user_id,) in users:
        try:
            await bot.send_message(user_id, broadcast_text, parse_mode="HTML")
            count += 1
        except Exception:
            # Если пользователь заблокировал бота, просто идем дальше
            continue
            
    await message.answer(f"✅ <b>Рассылка завершена!</b>\nОтправлено: {count} пользователям.")

@router.callback_query(F.data.startswith("lang:"))
async def set_lang(call: CallbackQuery):
    lang = call.data.split(":")[1]

    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute(
            "UPDATE users SET language=? WHERE user_id=?",
            (lang, call.from_user.id)
        )
        await db.commit()

    # сразу показываем главное меню
    await call.message.edit_text(
        TEXTS[lang]["main"],
        reply_markup=await main_menu_kb(call.from_user.id)
    )

    await call.answer()

# --- STARS MENU ---
@router.callback_query(F.data == "stars")
async def stars_menu(call: CallbackQuery):
    lang = await get_lang(call.from_user.id)

    # 1. Тексты описания
    text_map = {
        "ru": "⭐ <b>Оплата Telegram Stars</b>\n\nВыберите тариф ниже. Доступ будет предоставлен мгновенно.",
        "en": "⭐ <b>Telegram Stars Payment</b>\n\nChoose a plan below. Access will be granted instantly.",
        "es": "⭐ <b>Pago con Telegram Stars</b>\n\nElija un plan a continuación.",
        "de": "⭐ <b>Zahlung mit Telegram Stars</b>\n\nWählen Sie einen Tarif aus.",
        "fr": "⭐ <b>Paiement Telegram Stars</b>\n\nChoisissez une offre ci-dessous."
    }

    # 2. Словарь для перевода единиц времени на кнопках
    time_units = {
        "ru": {"1": "день", "7": "дней", "30": "дней"},
        "en": {"1": "day", "7": "days", "30": "days"},
        "es": {"1": "día", "7": "días", "30": "días"},
        "de": {"1": "Tag", "7": "Tage", "30": "Tage"},
        "fr": {"1": "jour", "7": "jours", "30": "jours"}
    }
    
    # Берем перевод для текущего языка (по умолчанию английский)
    units = time_units.get(lang, time_units["en"])

    # 3. Формируем кнопки
    kb_list = []
    for k, p in PLANS.items():
        # Извлекаем только число из названия (например, "1" из "1 день")
        days_count = "".join(filter(str.isdigit, p['name'])) 
        
        # Собираем новое название: Число + Переведенное слово
        translated_name = f"{days_count} {units.get(days_count, 'd.')}"
        
        kb_list.append([InlineKeyboardButton(
            text=f"{translated_name} — {p['stars']} ⭐",
            callback_data=f"stars_confirm:{k}"
        )])
    
    kb_list.append([InlineKeyboardButton(text="⬅ Back", callback_data="back")])
    
    kb = InlineKeyboardMarkup(inline_keyboard=kb_list)

    await call.message.edit_text(
        text_map.get(lang, text_map["en"]),
        reply_markup=kb,
        parse_mode="HTML"
    )
    await call.answer()

# --- STARS CONFIRM ---
@router.callback_query(F.data.startswith("stars_confirm:"))
async def stars_confirm(call: CallbackQuery):
    lang = await get_lang(call.from_user.id)

    plan_id = call.data.split(":")[1]
    plan = PLANS.get(plan_id)

    if not plan:
        await call.answer("❌ Error", show_alert=True)
        return

    try:
        invoice_link = await bot.create_invoice_link(
            title="Subscription",
            description=f"Access for {plan['name']}",
            payload=f"stars_{plan_id}",
            provider_token="",
            currency="XTR",
            prices=[LabeledPrice(label="Stars", amount=plan["stars"])]
        )
    except Exception as e:
        await call.answer("❌ Invoice error", show_alert=True)
        return

    text_map = {
        "ru": (
            f"📦 <b>{plan['name']}</b>\n"
            f"💰 {plan['stars']} ⭐\n\n"
            "👇 Нажмите кнопку ниже для оплаты"
        ),
        "en": (
            f"📦 <b>{plan['name']}</b>\n"
            f"💰 {plan['stars']} ⭐\n\n"
            "👇 Click the button below to pay"
        ),
        "es": (
            f"📦 <b>{plan['name']}</b>\n"
            f"💰 {plan['stars']} ⭐\n\n"
            "👇 Haz clic para pagar"
        ),
        "de": (
            f"📦 <b>{plan['name']}</b>\n"
            f"💰 {plan['stars']} ⭐\n\n"
            "👇 Klicke zum Bezahlen"
        ),
        "fr": (
            f"📦 <b>{plan['name']}</b>\n"
            f"💰 {plan['stars']} ⭐\n\n"
            "👇 Cliquez pour payer"
        ),
    }

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💸 Pay", url=invoice_link)],
        [InlineKeyboardButton(text="⬅ Back", callback_data="stars")]
    ])

    await call.message.edit_text(
        text_map.get(lang, text_map["en"]),
        reply_markup=kb,
        parse_mode="HTML"
    )

    await call.answer()

# --- CARD MENU ---
@router.callback_query(F.data == "pay_card")
async def pay_card(call: CallbackQuery):
    lang = await get_lang(call.from_user.id)

    # 1. Прописываем тексты прямо здесь, раз мы не создавали отдельный блок TEXTS
    text_map = {
        "ru": (
            "💳 <b>Выберите тариф:</b>\n\n"
            "💎 1 день — 690 рублей\n"
            "После оплаты вам придет ссылка на закрытый канал."
        ),
        "en": (
            "💳 <b>Choose a plan:</b>\n\n"
            "💎 1 day — 690 RUB\n"
            "⚠️ <b>Note:</b> SBP and Russian Cards work only with Russian banks. "
            "For international payments, please use <b>Stars</b> or <b>Crypto</b>."
        ),
        "es": (
            "💳 <b>Elige un plan:</b>\n\n"
            "💎 1 día — 690 RUB\n"
            "⚠️ <b>Nota:</b> El pago con tarjeta rusa solo funciona para bancos de Rusia. "
            "Use <b>Stars</b> o <b>Crypto</b> para pagos internacionales."
        ),
        "de": (
            "💳 <b>Tarif wählen:</b>\n\n"
            "💎 1 Tag — 690 RUB\n"
            "⚠️ <b>Hinweis:</b> Zahlungen mit russischen Karten funktionieren nur mit russischen Banken. "
            "Nutzen Sie <b>Stars</b> oder <b>Crypto</b>."
        ),
        "fr": (
            "💳 <b>Choisissez une offre:</b>\n\n"
            "💎 1 jour — 690 RUB\n"
            "⚠️ <b>Note:</b> Le paiement par carte russe ne fonctionne que pour les banques russes. "
            "Utilisez <b>Stars</b> ou <b>Crypto</b>."
        )
    }

    # 2. Формируем кнопки из твоего словаря PLANS
    kb_list = [
        [InlineKeyboardButton(
            text=f"{p['name']} — {p['rub']}₽",
            callback_data=f"card_confirm:{k}"
        )]
        for k, p in PLANS.items()
    ]
    
    # 3. Добавляем кнопку "Назад"
    kb_list.append([InlineKeyboardButton(text="⬅ Back", callback_data="back")])
    
    kb = InlineKeyboardMarkup(inline_keyboard=kb_list)

    # 4. Отправляем сообщение с поддержкой HTML
    await call.message.edit_text(
        text_map.get(lang, text_map["en"]), 
        reply_markup=kb,
        parse_mode="HTML"
    )
    await call.answer()

    
# --- START ---
@router.message(CommandStart())
async def start(message: Message):
    user_id = message.from_user.id
    args = message.text.split()

    # 1. Получаем данные пользователя из БД
    user = await get_user(user_id)

    # 2. Проверяем реферальную ссылку
    referrer = None
    if len(args) > 1 and args[1].isdigit():
        referrer = int(args[1])
        if referrer == user_id:
            referrer = None

    # 3. Если пользователя нет в базе (первый запуск)
    if not user:
        async with aiosqlite.connect(DB_NAME) as db:
            # Записываем пользователя в БД, но language ставим NULL, 
            # чтобы понять, что он еще не сделал выбор через кнопку.
            await db.execute("""
            INSERT INTO users (user_id, language, referrer)
            VALUES (?, NULL, ?)
            """, (user_id, referrer))
            await db.commit()
        
        # Отправляем меню выбора языка
        await message.answer(
            "🌍 Choose your language / Выберите язык",
            reply_markup=LANG_KB
        )
        return

    # 4. Если пользователь есть, смотрим его язык (индекс 7 в get_user)
    lang = user[7]
    
    # Если язык в БД сброшен (например, нажал /start, но не кликнул на кнопку языка в прошлый раз)
    if not lang:
        await message.answer(
            "🌍 Choose your language / Выберите язык",
            reply_markup=LANG_KB
        )
        return

    # 5. Пользователь уже есть и язык выбран — показываем сразу главное меню
    await message.answer(
        TEXTS[lang]["main"],
        reply_markup=await main_menu_kb(user_id)
    )


# --- BACK ---
@router.callback_query(F.data == "back")
async def back(call: CallbackQuery):
    lang = await get_lang(call.from_user.id)

    await call.message.edit_text(
        TEXTS[lang]["main"],
        reply_markup=await main_menu_kb(call.from_user.id)
    )


# --- JOIN HANDLER ---
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
                    f"✅ Access activated\n\n⏳ {days} days from now"
                )
            except:
                pass

    except Exception as e:
        logger.error(f"chat_member error: {e}")
# --- PLATEGA ---
@router.callback_query(F.data.startswith("card_confirm:"))
async def card_confirm(call: CallbackQuery):
    lang = await get_lang(call.from_user.id)

    plan_id = call.data.split(":")[1]
    plan = PLANS.get(plan_id)

    if not plan:
        await call.message.answer("❌ Error")
        return

    try:
        transaction_id = None
        pay_url = None

        # --- перевод текста ---
        loading_text = {
            "ru": "⏳ Подготовка платежа...",
            "en": "⏳ Preparing payment...",
            "es": "⏳ Preparando pago...",
            "de": "⏳ Zahlung wird vorbereitet...",
            "fr": "⏳ Préparation du paiement..."
        }

        # 1. ищем существующий платёж
        async with aiosqlite.connect(DB_NAME) as db:
            async with db.execute(
                "SELECT payload FROM card_invoices WHERE user_id=? AND plan_id=? AND status='pending'",
                (call.from_user.id, plan_id)
            ) as cur:
                existing = await cur.fetchone()

        # 2. проверка существующего платежа
        if existing:
            transaction_id = existing[0]

            async with http_session.get(
                f"https://app.platega.io/transaction/{transaction_id}",
                headers={
                    "X-MerchantId": MERCHANT_ID,
                    "X-Secret": PAYMENT_TOKEN
                }
            ) as resp:

                if resp.status == 200:
                    data = await resp.json()
                else:
                    data = {}

            pay_url = data.get("redirect")

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
                "description": f"TgId:{call.from_user.id}"
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

                text = await resp.text()

                try:
                    data = await resp.json()
                except Exception:
                    await call.message.answer("❌ Payment service error")
                    return

            transaction_id = data.get("transactionId")
            pay_url = data.get("redirect")

            if not transaction_id or not pay_url:
                await call.message.answer(f"❌ Platega error:\n{text}")
                return

            async with aiosqlite.connect(DB_NAME) as db:
                await db.execute(
                    "INSERT INTO card_invoices (payload, user_id, plan_id, status) VALUES (?, ?, ?, 'pending')",
                    (transaction_id, call.from_user.id, plan_id)
                )
                await db.commit()

        # 4. UX (ОДИН РАЗ — без двойного edit_text)
        await call.answer("⏳")

        await call.message.edit_text(
            loading_text.get(lang, loading_text["en"]),
            parse_mode="HTML"
        )

        text_map = {
            "ru": f"💳 <b>{plan['name']}</b>\n💰 {plan['rub']} ₽\n\n👇 Нажмите для оплаты",
            "en": f"💳 <b>{plan['name']}</b>\n💰 {plan['rub']} RUB\n\n👇 Click to pay",
            "es": f"💳 <b>{plan['name']}</b>\n💰 {plan['rub']} RUB\n\n👇 Paga aquí",
            "de": f"💳 <b>{plan['name']}</b>\n💰 {plan['rub']} RUB\n\n👇 Bezahlen",
            "fr": f"💳 <b>{plan['name']}</b>\n💰 {plan['rub']} RUB\n\n👇 Payer"
        }

        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="💸 Pay", url=pay_url)],
            [InlineKeyboardButton(text="⬅ Back", callback_data="pay_card")]
        ])

        await call.message.edit_text(
            text_map.get(lang, text_map["en"]),
            reply_markup=kb,
            parse_mode="HTML"
        )

    except Exception as e:
        logger.exception(f"PLATEGA ERROR: {e}")
        await call.message.answer("❌ Payment error")

    await call.answer()

# --- CRYPTO CONFIRM (FIXED STABLE VERSION) ---
@router.callback_query(F.data.startswith("crypto_confirm:"))
async def crypto_confirm(call: CallbackQuery):
    try:
        lang = await get_lang(call.from_user.id)

        plan_id = call.data.split(":")[1]
        plan = PLANS.get(plan_id)

        if not plan:
            await call.answer("Error", show_alert=True)
            return

        # отвечаем СРАЗУ (важно)
        await call.answer()

        time_units = {
            "ru": {"1": "день", "7": "дней", "30": "дней"},
            "en": {"1": "day", "7": "days", "30": "days"},
            "es": {"1": "día", "7": "días", "30": "días"},
            "de": {"1": "Tag", "7": "Tage", "30": "Tage"},
            "fr": {"1": "jour", "7": "jours", "30": "jours"}
        }

        units = time_units.get(lang, time_units["en"])
        days_count = str(plan["days"])
        translated_plan_name = f"{days_count} {units.get(days_count, 'd.')}"

        # loading
        await call.message.edit_text(
            {
                "ru": "💰 Создание инвойса...",
                "en": "💰 Creating invoice...",
                "es": "💰 Creando factura...",
                "de": "💰 Rechnung wird erstellt...",
                "fr": "💰 Création de facture..."
            }.get(lang, "💰 Creating invoice...")
        )

        # API
        async with http_session.post(
            "https://pay.crypt.bot/api/createInvoice",
            headers={"Crypto-Pay-API-Token": CRYPTO_TOKEN},
            json={
                "asset": "USDT",
                "amount": float(plan["crypto"]),
                "description": f"Subscription {translated_plan_name}"
            }
        ) as response:

            text_raw = await response.text()

            if response.status != 200:
                await call.message.answer("❌ Crypto API error")
                return

            data = await response.json()

        if not data.get("ok"):
            await call.message.answer("❌ Payment error")
            return

        result = data["result"]
        pay_url = result["pay_url"]
        invoice_id = str(result["invoice_id"])

        # save
        async with aiosqlite.connect(DB_NAME) as db:
            await db.execute(
                "INSERT OR IGNORE INTO crypto_invoices VALUES (?, ?, ?, 'pending')",
                (invoice_id, call.from_user.id, plan_id)
            )
            await db.commit()

        text_map = {
            "ru": (
                f"💰 <b>{translated_plan_name}</b>\n"
                f"💵 {plan['crypto']} USDT\n\n"
                "💡 После оплаты доступ активируется автоматически\n\n"
                "👇 Нажмите для оплаты"
            ),
            "en": (
                f"💰 <b>{translated_plan_name}</b>\n"
                f"💵 {plan['crypto']} USDT\n\n"
                "💡 After payment access activates automatically\n\n"
                "👇 Click to pay"
            )
        }

        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="💸 Pay", url=pay_url)],
            [InlineKeyboardButton(text="⬅ Back", callback_data="crypto")]
        ])

        await call.message.edit_text(
            text_map.get(lang, text_map["en"]),
            reply_markup=kb,
            parse_mode="HTML"
        )

    except Exception as e:
        logger.exception(f"crypto_confirm crash: {e}")
        try:
            await call.message.answer("❌ Payment error")
        except:
            pass
# --- REFERRAL ---
@router.callback_query(F.data == "ref")
async def ref(call: CallbackQuery):
    lang = await get_lang(call.from_user.id)

    user_data = await get_user(call.from_user.id)

    # безопасное извлечение (без падений)
    ref_count = user_data[3] or 0 if user_data else 0
    bonus_days = user_data[4] or 0 if user_data else 0

    # ⚡ лучше кешировать username (или хотя бы безопасно получать)
    try:
        bot_username = bot.username or (await bot.get_me()).username
    except Exception:
        bot_username = "your_bot"

    ref_link = f"https://t.me/{bot_username}?start={call.from_user.id}"

    texts = {
        "ru": (
            "<b>👥 Приглашай друзей — получай бонусы</b>\n\n"
            "За каждого друга, который оплатит подписку, ты получаешь <b>+7 дней доступа</b>.\n\n"
            "<b>📊 Твоя статистика:</b>\n"
            f"• Друзей: {ref_count}\n"
            f"• Бонус: +{bonus_days} дней\n\n"
            "<b>Твоя ссылка:</b>\n"
            f"<code>{ref_link}</code>"
        ),
        "en": (
            "<b>👥 Invite friends — earn rewards</b>\n\n"
            "For every friend who buys a subscription, you get <b>+7 extra days</b>.\n\n"
            "<b>📊 Your stats:</b>\n"
            f"• Friends: {ref_count}\n"
            f"• Bonus: +{bonus_days} days\n\n"
            "<b>Your link:</b>\n"
            f"<code>{ref_link}</code>"
        ),
        "es": (
            "<b>👥 Invita amigos — gana recompensas</b>\n\n"
            "Por cada amigo que pague, recibes <b>+7 días</b>.\n\n"
            f"<code>{ref_link}</code>"
        ),
        "de": (
            "<b>👥 Freunde einladen — Bonus erhalten</b>\n\n"
            "Für jeden zahlenden Freund bekommst du <b>+7 Tage</b>.\n\n"
            f"<code>{ref_link}</code>"
        ),
        "fr": (
            "<b>👥 Invite des amis — gagne des bonus</b>\n\n"
            "Chaque ami qui paie te donne <b>+7 jours</b>.\n\n"
            f"<code>{ref_link}</code>"
        ),
    }

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅ Back", callback_data="back")]
    ])

    await call.message.edit_text(
        texts.get(lang, texts["en"]),
        reply_markup=kb,
        parse_mode="HTML"
    )

    await call.answer()

# --- INFO ---

@router.callback_query(F.data == "info")
async def info(call: CallbackQuery):
    lang = await get_lang(call.from_user.id)

    texts = {
        "ru": "ℹ️ Информация\n\nВыберите раздел:",
        "en": "ℹ️ Information\n\nChoose a section:",
        "es": "ℹ️ Información\n\nElige una sección:",
        "de": "ℹ️ Informationen\n\nWähle einen Bereich:",
        "fr": "ℹ️ Informations\n\nChoisissez une section:",
    }

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📄 Privacy Policy", callback_data="privacy")],
        [InlineKeyboardButton(text="📜 Terms of Use", callback_data="terms")],
        [InlineKeyboardButton(text="⬅ Back", callback_data="back")]
    ])

    await call.message.edit_text(
        texts.get(lang, texts["en"]),
        reply_markup=kb
    )
    await call.answer()


@router.callback_query(F.data == "privacy")
async def privacy(call: CallbackQuery):
    lang = await get_lang(call.from_user.id)

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅ Back", callback_data="info")]
    ])

    await call.message.edit_text(
        PRIVACY_TEXT,
        reply_markup=kb
    )
    await call.answer()


@router.callback_query(F.data == "terms")
async def terms(call: CallbackQuery):
    lang = await get_lang(call.from_user.id)

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅ Back", callback_data="info")]
    ])

    await call.message.edit_text(
        TERMS_TEXT,
        reply_markup=kb
    )
    await call.answer()

# --- PAYMENTS & JOIN ---
JOIN_LINK = "https://t.me/+ffk7dB_5zPhkMWFk"

ADMIN_ID = os.getenv("ADMIN_ID")
if ADMIN_ID:
    ADMIN_ID = int(ADMIN_ID)


@router.pre_checkout_query()
async def pre_checkout(pre: PreCheckoutQuery):
    await pre.answer(ok=True)


@router.message(F.successful_payment)
async def success(message: Message):
    try:
        lang = await get_lang(message.from_user.id)

        payload = message.successful_payment.invoice_payload

        # ⭐ только Stars
        if not payload.startswith("stars_"):
            return

        plan_id = payload.split("_")[1]
        plan = PLANS.get(plan_id)

        if not plan:
            await message.answer("❌ Error")
            return

        days = plan["days"]

        # 🎯 защита от повторной обработки (idempotency)
        async with aiosqlite.connect(DB_NAME) as db:
            async with db.execute(
                "SELECT user_id FROM users WHERE user_id=? AND expiry IS NOT NULL",
                (message.from_user.id,)
            ) as cur:
                already = await cur.fetchone()

        # если хочешь строго — можно убрать этот блок
        await extend_user(message.from_user.id, days)

        # 🔔 ADMIN NOTIFY
        if ADMIN_ID:
            try:
                await notify_admin(
                    user_id=message.from_user.id,
                    plan_name=plan["name"],
                    method="Stars ⭐"
                )
            except Exception as e:
                logging.error(f"Admin notification error: {e}")

        # 🌍 тексты
        texts = {
            "ru": (
                "✅ Оплата прошла успешно!\n\n"
                f"🎉 Доступ активирован на <b>{days} дней</b>\n\n"
                "👇 Вступите в канал по кнопке ниже"
            ),
            "en": (
                "✅ Payment successful!\n\n"
                f"🎉 Access activated for <b>{days} days</b>\n\n"
                "👇 Join the channel below"
            ),
            "es": (
                "✅ Pago exitoso!\n\n"
                f"🎉 Acceso activado por <b>{days} días</b>\n\n"
                "👇 Entra al canal"
            ),
            "de": (
                "✅ Zahlung erfolgreich!\n\n"
                f"🎉 Zugang für <b>{days} Tage</b> aktiviert\n\n"
                "👇 Kanal beitreten"
            ),
            "fr": (
                "✅ Paiement réussi!\n\n"
                f"🎉 Accès activé pour <b>{days} jours</b>\n\n"
                "👇 Rejoindre le canal"
            ),
        }

        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(
                text="📢 Join Channel",
                url=JOIN_LINK
            )]
        ])

        await message.answer(
            texts.get(lang, texts["en"]),
            reply_markup=kb,
            parse_mode="HTML"
        )

    except Exception as e:
        logging.error(f"Stars success error: {e}")
        await message.answer("❌ Error processing payment")


JOIN_LINK = "https://t.me/+ffk7dB_5zPhkMWFk"

async def card_checker():
    while True:
        try:
            async with aiosqlite.connect(DB_NAME) as db:
                async with db.execute(
                    "SELECT payload, user_id, plan_id FROM card_invoices WHERE status='pending'"
                ) as cur:
                    invoices = await cur.fetchall()

            if not invoices:
                await asyncio.sleep(5)
                continue

            for transaction_id, user_id, plan_id in invoices:

                try:
                    # 🔒 сразу помечаем как processing (анти double trigger)
                    async with aiosqlite.connect(DB_NAME) as db:
                        cursor = await db.execute(
                            """
                            UPDATE card_invoices
                            SET status='processing'
                            WHERE payload=? AND status='pending'
                            """,
                            (transaction_id,)
                        )
                        await db.commit()

                    if cursor.rowcount == 0:
                        continue

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

                    if status not in ("CONFIRMED", "SUCCESS", "PAID"):
                        # возвращаем обратно pending
                        async with aiosqlite.connect(DB_NAME) as db:
                            await db.execute(
                                "UPDATE card_invoices SET status='pending' WHERE payload=?",
                                (transaction_id,)
                            )
                            await db.commit()
                        continue

                    days = PLANS[plan_id]["days"]

                    await extend_user(user_id, days)

                    if ADMIN_ID:
                        try:
                            await notify_admin(
                                user_id=user_id,
                                plan_name=PLANS[plan_id]["name"],
                                method="Card / SBP 💳",
                                extra=f"Tx: <code>{transaction_id}</code>"
                            )
                        except Exception as e:
                            logger.error(f"Admin notify error: {e}")

                    text = (
                        "✅ Payment successful!\n\n"
                        f"🎉 Access: <b>{days} days</b>\n\n"
                        "👇 Join the channel below"
                    )

                    kb = InlineKeyboardMarkup(inline_keyboard=[
                        [InlineKeyboardButton(
                            text="📢 Join Channel",
                            url=JOIN_LINK
                        )]
                    ])

                    await bot.send_message(
                        user_id,
                        text,
                        reply_markup=kb,
                        parse_mode="HTML"
                    )

                except Exception as e:
                    logger.error(f"Card inner error: {e}")

        except Exception as e:
            logger.error(f"Card checker loop error: {e}")

        await asyncio.sleep(5)

async def crypto_checker():
    while True:
        try:
            async with aiosqlite.connect(DB_NAME) as db:
                async with db.execute(
                    "SELECT invoice_id, user_id, plan_id FROM crypto_invoices WHERE status='pending'"
                ) as cur:
                    invoices = await cur.fetchall()

            if not invoices:
                await asyncio.sleep(15)
                continue

            for inv_id, user_id, plan_id in invoices:

                try:
                    # 🔒 блокируем обработку сразу
                    async with aiosqlite.connect(DB_NAME) as db:
                        cursor = await db.execute(
                            """
                            UPDATE crypto_invoices
                            SET status='processing'
                            WHERE invoice_id=? AND status='pending'
                            """,
                            (inv_id,)
                        )
                        await db.commit()

                    if cursor.rowcount == 0:
                        continue

                    async with http_session.get(
                        "https://pay.crypt.bot/api/getInvoices",
                        headers={"Crypto-Pay-API-Token": CRYPTO_TOKEN},
                        params={"invoice_ids": inv_id}
                    ) as resp:

                        if resp.status != 200:
                            logger.error(f"Crypto HTTP error: {resp.status}")
                            continue

                        data = await resp.json()

                    if not isinstance(data, dict) or not data.get("ok"):
                        logger.error(f"Crypto API error: {data}")
                        continue

                    items = data.get("result", {}).get("items", [])
                    if not items:
                        continue

                    status = items[0].get("status")

                    if status != "paid":
                        # вернуть обратно pending
                        async with aiosqlite.connect(DB_NAME) as db:
                            await db.execute(
                                "UPDATE crypto_invoices SET status='pending' WHERE invoice_id=?",
                                (inv_id,)
                            )
                            await db.commit()
                        continue

                    days = PLANS[plan_id]["days"]

                    await extend_user(user_id, days)

                    if ADMIN_ID:
                        try:
                            await notify_admin(
                                user_id=user_id,
                                plan_name=PLANS[plan_id]["name"],
                                method="Crypto 💰",
                                extra=f"Invoice: <code>{inv_id}</code>"
                            )
                        except Exception as e:
                            logger.error(f"Admin notify error: {e}")

                    text = (
                        "✅ Crypto payment confirmed!\n\n"
                        f"🎉 Access: <b>{days} days</b>\n\n"
                        "👇 Join the channel below"
                    )

                    kb = InlineKeyboardMarkup(inline_keyboard=[
                        [InlineKeyboardButton(
                            text="📢 Join Channel",
                            url=JOIN_LINK
                        )]
                    ])

                    await bot.send_message(
                        user_id,
                        text,
                        reply_markup=kb,
                        parse_mode="HTML"
                    )

                except Exception as e:
                    logger.error(f"Crypto inner error: {e}")

        except Exception as e:
            logger.error(f"Crypto checker loop error: {e}")

        await asyncio.sleep(15)

# ================== SUBSCRIPTION CHECKER ==================
async def check_subscriptions():
    while True:
        try:
            # Открываем базу один раз для всего цикла проверки
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

                        expiry_dt = datetime.fromisoformat(expiry_str)
                        if expiry_dt.tzinfo is None:
                            expiry_dt = expiry_dt.replace(tzinfo=timezone.utc)

                        if now <= expiry_dt:
                            continue

                        # ❌ Доступ истёк → удаляем из канала
                        try:
                            # Убираем из канала
                            await bot.ban_chat_member(
                                chat_id=CHANNEL_ID,
                                user_id=user_id,
                                revoke_messages=False
                            )
                            # Сразу разбаниваем, чтобы мог зайти снова после оплаты
                            await asyncio.sleep(0.2) 
                            await bot.unban_chat_member(
                                chat_id=CHANNEL_ID,
                                user_id=user_id
                            )
                        except TelegramBadRequest as e:
                            if "not found" not in str(e).lower():
                                logger.error(f"Ban error {user_id}: {e}")

                        # Обновляем БД (используем уже открытое соединение 'db')
                        await db.execute(
                            "UPDATE users SET expiry=NULL WHERE user_id=?",
                            (user_id,)
                        )
                        await db.commit()

                        # Уведомляем пользователя
                        try:
                            await bot.send_message(
                                user_id,
                                "❌ Подписка закончилась.\n"
                                "Вы были удалены из канала.\n"
                                "Оплатите подписку снова, чтобы вернуть доступ."
                            )
                        except Exception:
                            # Если заблокировал бота — просто игнорируем
                            pass

                    except Exception as e:
                        logger.error(f"User check error {user_id}: {e}")

        except Exception as e:
            logger.error(f"Subscription checker error: {e}")

        # Проверка раз в час
        await asyncio.sleep(3600)


# ================== MAIN ==================
async def main():
    global http_session

    try:
        http_session = aiohttp.ClientSession()

        await init_db()

        loop = asyncio.get_running_loop()

        # фоновые задачи
        tasks.append(loop.create_task(crypto_checker(), name="crypto_checker"))
        tasks.append(loop.create_task(card_checker(), name="card_checker"))
        tasks.append(loop.create_task(check_subscriptions(), name="subscription_checker"))

        logger.info("Bot started successfully")

        await dp.start_polling(bot)

    except Exception as e:
        logger.exception(f"FATAL ERROR IN MAIN: {e}")

    finally:
        logger.info("Shutting down...")

        for task in tasks:
            task.cancel()

        await asyncio.gather(*tasks, return_exceptions=True)

        if http_session and not http_session.closed:
            await http_session.close()

        await bot.session.close()

        logger.info("Bot stopped cleanly")

if __name__ == "__main__":
    asyncio.run(main())
