import asyncio
import logging
import os
import requests
import sqlite3
from datetime import datetime, timedelta
from aiogram import Bot, Dispatcher, types

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

API_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
GROUP_ID = os.getenv("TELEGRAM_GROUP_ID") or os.getenv("TELEGRAM_CHANNEL_ID")
CRYPTO_TOKEN = os.getenv("CRYPTO_TOKEN")
ADMIN_ID = os.getenv("ADMIN_ID")

try:
    ADMIN_ID = int(ADMIN_ID) if ADMIN_ID else None
except:
    ADMIN_ID = None


def is_admin(user_id: int) -> bool:
    return ADMIN_ID is not None and user_id == ADMIN_ID

PLANS = {
    "plan_1": {"amount": 550, "title": "1 день доступа", "label": "1 день", "days": 1},
    "plan_7": {"amount": 770, "title": "7 дней доступа", "label": "7 дней", "days": 7},
    "plan_30": {"amount": 1100, "title": "30 дней доступа", "label": "30 дней", "days": 30},
}


class CryptoPayError(Exception):
    pass


def check_invoice(invoice_id):
    if not CRYPTO_TOKEN:
        raise CryptoPayError("CRYPTO_TOKEN не настроен")

    url = "https://pay.crypt.bot/api/getInvoices"
    headers = {"Crypto-Pay-API-Token": CRYPTO_TOKEN}
    params = {"invoice_ids": invoice_id}

    try:
        response = requests.get(url, headers=headers, params=params, timeout=15)
    except requests.exceptions.RequestException as e:
        raise CryptoPayError(f"сеть недоступна: {e}")

    try:
        data = response.json()
    except ValueError:
        raise CryptoPayError(f"некорректный ответ API ({response.status_code})")

    if not data.get("ok"):
        raise CryptoPayError(f"API вернул ошибку: {data.get('error')}")

    items = data.get("result", {}).get("items") or []

    if not items:
        raise CryptoPayError("счёт не найден")

    return items[0]["status"]


def create_invoice(amount, payload):
    if not CRYPTO_TOKEN:
        raise CryptoPayError("CRYPTO_TOKEN не настроен")

    url = "https://pay.crypt.bot/api/createInvoice"
    headers = {"Crypto-Pay-API-Token": CRYPTO_TOKEN}
    data = {
        "asset": "USDT",
        "amount": amount,
        "description": payload,
    }

    try:
        response = requests.post(url, headers=headers, json=data, timeout=15)
    except requests.exceptions.RequestException as e:
        raise CryptoPayError(f"сеть недоступна: {e}")

    try:
        body = response.json()
    except ValueError:
        raise CryptoPayError(f"некорректный ответ API ({response.status_code})")

    if not body.get("ok"):
        raise CryptoPayError(f"API вернул ошибку: {body.get('error')}")

    result = body.get("result")

    if not result or "invoice_id" not in result or "pay_url" not in result:
        raise CryptoPayError("не удалось создать счёт")

    return result

conn = sqlite3.connect("users.db")
cursor = conn.cursor()

cursor.execute(
    """
    CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        expire_date TEXT,
        ref_by INTEGER,
        refs_paid INTEGER DEFAULT 0
    )
    """
)

cursor.execute(
    """
    CREATE TABLE IF NOT EXISTS payments (
        invoice_id TEXT,
        user_id INTEGER,
        days INTEGER,
        status TEXT
    )
    """
)

cursor.execute(
    """
    CREATE TABLE IF NOT EXISTS payments_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        method TEXT,
        days INTEGER,
        amount REAL,
        currency TEXT,
        created_at TEXT
    )
    """
)


def log_payment(user_id: int, method: str, days: int, amount: float, currency: str):
    cursor.execute(
        "INSERT INTO payments_log (user_id, method, days, amount, currency, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (user_id, method, days, amount, currency, datetime.now().isoformat()),
    )
    conn.commit()


STARS_PRICES = {1: 550, 7: 770, 30: 1100}
CRYPTO_PRICES = {1: 5, 7: 7, 30: 10}

INVOICE_COOLDOWN = 60
last_invoice_at: dict[int, float] = {}


def check_invoice_cooldown(user_id: int) -> int:
    import time
    now = time.time()
    last = last_invoice_at.get(user_id, 0)
    elapsed = now - last
    if elapsed < INVOICE_COOLDOWN:
        return int(INVOICE_COOLDOWN - elapsed)
    return 0


def mark_invoice_created(user_id: int):
    import time
    last_invoice_at[user_id] = time.time()

cursor.execute("PRAGMA table_info(users)")
columns = [column[1] for column in cursor.fetchall()]

try:
    cursor.execute("ALTER TABLE users ADD COLUMN ref_by INTEGER")
    cursor.execute("ALTER TABLE users ADD COLUMN refs_paid INTEGER DEFAULT 0")
    conn.commit()
except:
    pass

if "refs" not in columns:
    cursor.execute(
        """
        ALTER TABLE users ADD COLUMN refs INTEGER DEFAULT 0
        """
    )

if "ref_bonus_paid" not in columns:
    cursor.execute(
        """
        ALTER TABLE users ADD COLUMN ref_bonus_paid INTEGER DEFAULT 0
        """
    )

if "notified" not in columns:
    try:
        cursor.execute(
            """
            ALTER TABLE users ADD COLUMN notified INTEGER DEFAULT 0
            """
        )
    except:
        pass

conn.commit()


def has_required_config() -> bool:
    missing = [
        name
        for name, value in {
            "TELEGRAM_BOT_TOKEN": API_TOKEN,
            "TELEGRAM_GROUP_ID": GROUP_ID,
        }.items()
        if not value
    ]

    if missing:
        logger.warning("Telegram bot is waiting for configuration: %s", ", ".join(missing))
        return False

    return True


async def wait_for_configuration() -> None:
    while True:
        await asyncio.sleep(3600)


if not has_required_config():
    asyncio.run(wait_for_configuration())

bot = Bot(token=API_TOKEN)
dp = Dispatcher()


def get_plan_keyboard() -> InlineKeyboardMarkup:
    kb = InlineKeyboardMarkup(row_width=1)
    kb.add(
        InlineKeyboardButton("1 день — 550⭐", callback_data="plan_1"),
        InlineKeyboardButton("7 дней — 770⭐", callback_data="plan_7"),
        InlineKeyboardButton("30 дней — 1100⭐", callback_data="plan_30"),
        InlineKeyboardButton("⬅ Назад", callback_data="back_main"),
    )
    return kb


def get_start_keyboard() -> InlineKeyboardMarkup:
    kb = InlineKeyboardMarkup(row_width=1)
    kb.add(
        InlineKeyboardButton("Оплата Telegram Stars ⭐", callback_data="stars_menu"),
        InlineKeyboardButton("Оплата Crypto 💰", callback_data="crypto_menu"),
        InlineKeyboardButton("Реферальная ссылка 🎁", callback_data="ref_link"),
    )
    return kb


@dp.message_handler(commands=["start"])
async def start(message: types.Message):
    args = message.get_args()

    if args.isdigit():
        ref_id = int(args)

        if ref_id != message.from_user.id:
            cursor.execute("SELECT user_id FROM users WHERE user_id=?", (message.from_user.id,))
            exists = cursor.fetchone()

            if not exists:
                cursor.execute(
                    """
                    INSERT INTO users (user_id, ref_by)
                    VALUES (?, ?)
                    """,
                    (message.from_user.id, ref_id),
                )
                conn.commit()

    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(
        InlineKeyboardButton("Оплата ⭐️", callback_data="stars_menu"),
        InlineKeyboardButton("Crypto 💰", callback_data="crypto_menu"),
    )
    kb.add(
        InlineKeyboardButton("🎁 Реферал", callback_data="ref_menu"),
        InlineKeyboardButton("📅 Моя подписка", callback_data="my_sub"),
    )
    kb.add(
        InlineKeyboardButton("ℹ️ Информация", callback_data="info_menu"),
    )

    await message.answer(
        "🔒 Добро пожаловать в закрытый канал MistyBibi\n\n"
        "Здесь доступен эксклюзивный контент, которого нет в открытом доступе.\n\n"
        "💎 Что тебя ждёт:\n"
        "— расширенный контент\n"
        "— регулярные обновления\n"
        "— контент только для подписчиков\n\n"
        "⚡ Доступ открывается после оплаты\n\n"
        "Выбери действие ниже:",
        reply_markup=kb,
    )


@dp.message_handler(commands=["users"])
async def users(message: types.Message):
    cursor.execute("SELECT user_id, expire_date FROM users")
    rows = cursor.fetchall()

    text = "Список клиентов:\n\n"

    for user_id, expire in rows:
        text += f"{user_id} — до {expire}\n"

    await message.answer(text)


@dp.message_handler(commands=["refstats"])
async def refstats(message: types.Message):
    cursor.execute(
        "SELECT refs_paid FROM users WHERE user_id=?",
        (message.from_user.id,),
    )

    row = cursor.fetchone()
    count = row[0] if row else 0

    await message.answer(f"Ты пригласил {count} оплативших пользователей")


@dp.callback_query_handler(lambda c: c.data == "ref_stats")
async def ref_stats(call: types.CallbackQuery):
    await call.answer()

    cursor.execute("""
        SELECT refs_paid FROM users WHERE user_id=?
    """, (call.from_user.id,))

    row = cursor.fetchone()
    count = row[0] if row else 0

    kb = InlineKeyboardMarkup(row_width=1)
    kb.add(InlineKeyboardButton("⬅ Назад", callback_data="back_plan"))

    await call.message.answer(
        f"📊 Статистика рефералов:\n\n"
        f"Оплативших друзей: {count}\n"
        f"Бонус начисляется за каждого оплатившего пользователя",
        reply_markup=kb,
    )


@dp.callback_query_handler(lambda c: c.data == "renew")
async def renew(call: types.CallbackQuery):
    await call.answer()

    kb = InlineKeyboardMarkup(row_width=1)

    kb.add(
        InlineKeyboardButton("1 день — 550⭐", callback_data="plan_1"),
        InlineKeyboardButton("7 дней — 770⭐", callback_data="plan_7"),
        InlineKeyboardButton("30 дней — 1100⭐", callback_data="plan_30"),
        InlineKeyboardButton("Реферальная ссылка 🎁", callback_data="ref_link"),
        InlineKeyboardButton("⬅ Назад", callback_data="back_plan"),
    )

    await call.message.answer("Выбери продление:", reply_markup=kb)


@dp.callback_query_handler(lambda c: c.data == "ref_menu")
async def ref_menu(call: types.CallbackQuery):
    await call.answer()

    text = (
        "🎁 РЕФЕРАЛЬНАЯ ПРОГРАММА\n\n"
        "Приглашай друзей и получай бесплатный доступ к закрытому каналу.\n\n"
        "📌 Как это работает:\n"
        "1. Отправь другу свою реферальную ссылку\n"
        "2. Друг оплачивает подписку\n"
        "3. Ты получаешь +7 дней доступа\n\n"
        "💡 Система накопительная:\n"
        "Каждый оплативший друг продлевает твою подписку.\n\n"
        "🚀 Чем больше друзей — тем дольше бесплатный доступ"
    )

    kb = InlineKeyboardMarkup(row_width=1)
    kb.add(
        InlineKeyboardButton("📎 Получить реферальную ссылку", callback_data="ref_link"),
        InlineKeyboardButton("📊 Моя статистика", callback_data="ref_stats"),
        InlineKeyboardButton("⬅ Назад", callback_data="back_main"),
    )

    await call.message.answer(text, reply_markup=kb)


@dp.callback_query_handler(lambda c: c.data == "ref_link")
async def ref_link(call: types.CallbackQuery):
    await call.answer()

    bot_info = await bot.get_me()
    link = f"https://t.me/{bot_info.username}?start={call.from_user.id}"

    kb = InlineKeyboardMarkup(row_width=1)
    kb.add(
        InlineKeyboardButton("⬅ Назад", callback_data="back_plan"),
    )

    await call.message.answer(
        f"🔗 Ваша реферальная ссылка:\n\n{link}",
        reply_markup=kb,
    )


def get_subscription_text(user_id: int) -> str:
    cursor.execute("SELECT expire_date FROM users WHERE user_id=?", (user_id,))
    row = cursor.fetchone()

    if not row or not row[0]:
        return (
            "📅 МОЯ ПОДПИСКА\n\n"
            "У тебя нет активной подписки.\n"
            "Оформи доступ через меню оплаты."
        )

    try:
        expire_dt = datetime.fromisoformat(row[0])
    except:
        return (
            "📅 МОЯ ПОДПИСКА\n\n"
            "У тебя нет активной подписки.\n"
            "Оформи доступ через меню оплаты."
        )

    now = datetime.now()
    delta = expire_dt - now

    if delta.total_seconds() <= 0:
        return (
            "📅 МОЯ ПОДПИСКА\n\n"
            "Срок действия истёк.\n"
            "Продли подписку, чтобы вернуть доступ."
        )

    days = delta.days
    hours = delta.seconds // 3600

    if days > 0:
        left = f"{days} дн. {hours} ч."
    else:
        minutes = (delta.seconds % 3600) // 60
        left = f"{hours} ч. {minutes} мин."

    return (
        "📅 МОЯ ПОДПИСКА\n\n"
        f"✅ Статус: активна\n"
        f"⏳ Осталось: {left}\n"
        f"📆 Действует до: {expire_dt.strftime('%d.%m.%Y %H:%M')}"
    )


@dp.message_handler(commands=["sub"])
async def sub_cmd(message: types.Message):
    kb = InlineKeyboardMarkup(row_width=1)
    kb.add(
        InlineKeyboardButton("🔁 Продлить подписку", callback_data="renew"),
        InlineKeyboardButton("⬅ Назад", callback_data="back_plan"),
    )

    await message.answer(get_subscription_text(message.from_user.id), reply_markup=kb)


@dp.callback_query_handler(lambda c: c.data == "my_sub")
async def my_sub(call: types.CallbackQuery):
    await call.answer()

    kb = InlineKeyboardMarkup(row_width=1)
    kb.add(
        InlineKeyboardButton("🔁 Продлить подписку", callback_data="renew"),
        InlineKeyboardButton("⬅ Назад", callback_data="back_plan"),
    )

    await call.message.answer(get_subscription_text(call.from_user.id), reply_markup=kb)


@dp.callback_query_handler(lambda c: c.data == "info_menu")
async def info_menu(call: types.CallbackQuery):
    await call.answer()

    kb = InlineKeyboardMarkup(row_width=1)
    kb.add(
        InlineKeyboardButton("📄 Политика конфиденциальности", callback_data="policy"),
        InlineKeyboardButton("📑 Пользовательское соглашение", callback_data="terms"),
        InlineKeyboardButton("💬 Поддержка", url="https://t.me/mistybibi"),
        InlineKeyboardButton("⬅ Назад", callback_data="back_plan"),
    )

    await call.message.answer("ℹ️ Информация:", reply_markup=kb)


@dp.callback_query_handler(lambda c: c.data == "policy")
async def policy(call: types.CallbackQuery):
    await call.answer()

    text = (
        "📄 ПОЛИТИКА КОНФИДЕНЦИАЛЬНОСТИ\n\n"
        "1. Общие положения\n"
        "1.1. Настоящая Политика конфиденциальности (далее — «Политика») регулирует "
        "порядок обработки и защиты информации, которую Пользователь передаёт при "
        "использовании сервиса (далее — «Сервис»).\n"
        "1.2. Используя Сервис, Пользователь подтверждает своё согласие с условиями "
        "Политики. Если Пользователь не согласен с условиями — он обязан прекратить "
        "использование Сервиса.\n\n"
        "2. Сбор информации\n"
        "2.1. Сервис может собирать следующие типы данных:\n"
        "— идентификаторы аккаунта (логин, ID, никнейм и т.п.);\n"
        "— техническую информацию (IP-адрес, данные о браузере, устройстве и ОС);\n"
        "— историю взаимодействий с Сервисом.\n"
        "2.2. Сервис не требует от Пользователя предоставления паспортных данных, "
        "документов, фотографий или другой личной информации, кроме минимально "
        "необходимой для работы.\n\n"
        "3. Использование информации\n"
        "3.1. Сервис может использовать полученную информацию исключительно для:\n"
        "— обеспечения работы функционала;\n"
        "— связи с Пользователем (в том числе для уведомлений и поддержки);\n"
        "— анализа и улучшения работы Сервиса.\n\n"
        "4. Передача информации третьим лицам\n"
        "4.1. Администрация не передаёт полученные данные третьим лицам, за "
        "исключением случаев:\n"
        "— если это требуется по закону;\n"
        "— если это необходимо для исполнения обязательств перед Пользователем "
        "(например, при работе с платёжными системами);\n"
        "— если Пользователь сам дал на это согласие.\n\n"
        "5. Хранение и защита данных\n"
        "5.1. Данные хранятся в течение срока, необходимого для достижения целей "
        "обработки.\n"
        "5.2. Администрация принимает разумные меры для защиты данных, но не "
        "гарантирует абсолютную безопасность информации при передаче через интернет.\n\n"
        "6. Отказ от ответственности\n"
        "6.1. Пользователь понимает и соглашается, что передача информации через "
        "интернет всегда сопряжена с рисками.\n"
        "6.2. Администрация не несёт ответственности за утрату, кражу или раскрытие "
        "данных, если это произошло по вине третьих лиц или самого Пользователя.\n\n"
        "7. Изменения в Политике\n"
        "7.1. Администрация вправе изменять условия Политики без предварительного "
        "уведомления.\n"
        "7.2. Продолжение использования Сервиса после внесения изменений означает "
        "согласие Пользователя с новой редакцией Политики."
    )

    kb = InlineKeyboardMarkup(row_width=1)
    kb.add(InlineKeyboardButton("⬅ Назад", callback_data="back_plan"))

    await call.message.answer(text, reply_markup=kb)


@dp.callback_query_handler(lambda c: c.data == "terms")
async def terms(call: types.CallbackQuery):
    await call.answer()

    text = (
        "📑 ПОЛЬЗОВАТЕЛЬСКОЕ СОГЛАШЕНИЕ\n\n"
        "1. Общие положения\n"
        "1.1. Настоящее Пользовательское соглашение (далее — «Соглашение») регулирует "
        "порядок использования онлайн-сервиса (далее — «Сервис»), предоставляемого "
        "Администрацией.\n"
        "1.2. Используя Сервис, включая запуск бота, регистрацию, оплату услуг или "
        "получение доступа к материалам, Пользователь подтверждает, что полностью "
        "ознакомился с условиями настоящего Соглашения и принимает их в полном объёме.\n"
        "1.3. В случае несогласия с условиями Соглашения Пользователь обязан "
        "прекратить использование Сервиса.\n\n"
        "2. Характер услуг и цифровых товаров\n"
        "2.1. Сервис предоставляет цифровые товары и услуги нематериального характера, "
        "включая, но не ограничиваясь: информационные материалы, обучающие программы, "
        "консультации, цифровые продукты и сервисные услуги.\n"
        "2.2. Материалы, предоставляемые через Сервис, могут включать:\n"
        "— информацию из открытых источников;\n"
        "— авторские материалы Администрации и/или третьих лиц;\n"
        "— аналитические обзоры, подборки, рекомендации, структурированные данные.\n"
        "2.3. Пользователь осознаёт и соглашается, что ценность цифровых товаров и "
        "услуг Сервиса заключается в систематизации, анализе, форме подачи, "
        "сопровождении, поддержке и обновлениях, а не в эксклюзивности отдельных "
        "фрагментов информации.\n"
        "2.4. Сервис не заявляет и не гарантирует уникальность, исключительность или "
        "недоступность отдельных элементов материалов вне Сервиса.\n\n"
        "3. Отказ от гарантий и ответственности\n"
        "3.1. Сервис предоставляется на условиях «AS IS» («как есть»).\n"
        "3.2. Администрация не гарантирует:\n"
        "— соответствие Сервиса ожиданиям Пользователя;\n"
        "— достижение каких-либо финансовых, коммерческих, профессиональных или иных "
        "результатов;\n"
        "— бесперебойную и безошибочную работу Сервиса.\n"
        "3.3. Администрация не несёт ответственности за:\n"
        "— любые прямые или косвенные убытки, включая упущенную выгоду;\n"
        "— последствия применения Пользователем полученных материалов;\n"
        "— действия или бездействие третьих лиц;\n"
        "— временные технические сбои и ограничения доступа.\n"
        "3.4. Все решения о применении материалов, рекомендаций и услуг принимаются "
        "Пользователем самостоятельно и на его риск.\n\n"
        "4. Законность использования\n"
        "4.1. Сервис не предназначен для поощрения, организации или содействия "
        "противоправной деятельности.\n"
        "4.2. Пользователь обязуется использовать Сервис исключительно в рамках "
        "применимого законодательства и правил третьих сторон.\n"
        "4.3. Ответственность за законность использования материалов и услуг Сервиса "
        "полностью возлагается на Пользователя.\n\n"
        "5. Интеллектуальная собственность\n"
        "5.1. Все материалы, размещённые в Сервисе, охраняются законодательством об "
        "интеллектуальной собственности.\n"
        "5.2. Пользователю запрещается копировать, распространять, перепродавать, "
        "передавать третьим лицам или иным образом использовать материалы Сервиса без "
        "разрешения правообладателя.\n"
        "5.3. Нарушение прав интеллектуальной собственности может повлечь ограничение "
        "доступа к Сервису без компенсации.\n\n"
        "6. Ограничение доступа\n"
        "6.1. Администрация вправе приостановить или ограничить доступ Пользователя к "
        "Сервису в случае:\n"
        "— нарушения условий настоящего Соглашения;\n"
        "— выявления злоупотреблений;\n"
        "— требований законодательства или платёжных провайдеров.\n"
        "6.2. Ограничение доступа не освобождает Пользователя от обязательств, "
        "возникших ранее.\n"
        "6.3. Администрация оставляет за собой право отказывать в обслуживании "
        "Пользователям, чьи действия могут создавать повышенные риски для Сервиса, "
        "платёжных провайдеров или третьих лиц.\n\n"
        "7. Платежи и возвраты\n"
        "7.1. Оплата услуг и цифровых товаров производится на условиях, указанных в "
        "Сервисе до момента оплаты.\n"
        "7.2. В связи с нематериальным характером цифровых товаров и услуг, возврат "
        "денежных средств после предоставления доступа не осуществляется, за "
        "исключением случаев, указанных ниже.\n"
        "7.3. Возврат средств возможен только если:\n"
        "— услуга не была оказана по технической вине Сервиса;\n"
        "— доступ к цифровому товару фактически не был предоставлен.\n"
        "7.4. Для рассмотрения вопроса о возврате Пользователь обязан обратиться в "
        "службу поддержки в течение 24 часов с момента оплаты.\n"
        "7.5. Решение о возврате принимается Администрацией индивидуально."
    )

    kb = InlineKeyboardMarkup(row_width=1)
    kb.add(InlineKeyboardButton("⬅ Назад", callback_data="back_plan"))

    await call.message.answer(text, reply_markup=kb)


@dp.callback_query_handler(lambda c: c.data == "stars_menu")
async def stars_menu(call: types.CallbackQuery):
    await call.message.answer("Выбери тариф:", reply_markup=get_plan_keyboard())
    await call.answer()


@dp.callback_query_handler(lambda c: c.data == "crypto_menu")
async def crypto_menu(call: types.CallbackQuery):
    kb = InlineKeyboardMarkup(row_width=1)

    kb.add(
        InlineKeyboardButton("1 день — 6,5 USDT", callback_data="crypto_1"),
        InlineKeyboardButton("7 дней — 9 USDT", callback_data="crypto_7"),
        InlineKeyboardButton("30 дней — 13 USDT", callback_data="crypto_30"),
        InlineKeyboardButton("⬅ Назад", callback_data="back_main"),
    )

    await call.message.answer("Оплата криптой:", reply_markup=kb)
    await call.answer()


@dp.callback_query_handler(lambda c: c.data in ("crypto_1", "crypto_7", "crypto_30"))
async def crypto_pay(call: types.CallbackQuery):
    if call.data == "crypto_1":
        amount = 5
        days = 1
    elif call.data == "crypto_7":
        amount = 7
        days = 7
    elif call.data == "crypto_30":
        amount = 10
        days = 30

    wait = check_invoice_cooldown(call.from_user.id)
    if wait > 0:
        await call.answer(
            f"Подожди {wait} сек. перед созданием нового счёта",
            show_alert=True,
        )
        return

    try:
        invoice = create_invoice(amount, f"{days}_days")
    except CryptoPayError as e:
        logger.warning("create_invoice failed: %s", e)
        await call.answer()
        await call.message.answer(
            "⚠️ Платёжный сервис временно недоступен.\n"
            "Попробуй ещё раз через пару минут или оплати через ⭐ Telegram Stars."
        )
        return

    invoice_id = invoice["invoice_id"]
    pay_url = invoice["pay_url"]

    cursor.execute("""
        INSERT INTO payments (invoice_id, user_id, days, status)
        VALUES (?, ?, ?, ?)
    """, (invoice_id, call.from_user.id, days, "pending"))
    conn.commit()

    mark_invoice_created(call.from_user.id)

    kb = InlineKeyboardMarkup().add(
        InlineKeyboardButton("Я оплатил ✅", callback_data="check_crypto")
    )

    await call.message.answer(f"Оплати по ссылке:\n{pay_url}", reply_markup=kb)
    await call.answer()


@dp.callback_query_handler(lambda c: c.data == "check_crypto")
async def check_crypto(call: types.CallbackQuery):
    await call.message.delete()
    await call.answer()

    cursor.execute(
        "SELECT invoice_id, days FROM payments WHERE user_id=? AND status='pending' ORDER BY rowid DESC LIMIT 1",
        (call.from_user.id,),
    )
    row = cursor.fetchone()

    if not row:
        await call.message.answer("Активный счёт не найден.")
        return

    invoice_id, days = row

    try:
        status = check_invoice(invoice_id)
    except CryptoPayError as e:
        logger.warning("check_invoice failed: %s", e)
        await call.message.answer(
            "⚠️ Не удалось проверить оплату — платёжный сервис недоступен.\n"
            "Попробуй чуть позже, твой счёт сохранён."
        )
        return

    if status != "paid":
        await call.message.answer("Оплата ещё не поступила. Попробуй чуть позже.")
        return

    cursor.execute(
        "UPDATE payments SET status='paid' WHERE invoice_id=?",
        (invoice_id,),
    )

    expire = datetime.now() + timedelta(days=days)

    cursor.execute("SELECT ref_by, ref_bonus_paid FROM users WHERE user_id=?", (call.from_user.id,))
    user_row = cursor.fetchone()

    if user_row:
        ref_id, ref_bonus_paid = user_row
        cursor.execute(
            "UPDATE users SET expire_date=?, notified=0 WHERE user_id=?",
            (expire.isoformat(), call.from_user.id),
        )
    else:
        ref_id = None
        ref_bonus_paid = 0
        cursor.execute(
            "INSERT INTO users (user_id, expire_date, notified) VALUES (?, ?, 0)",
            (call.from_user.id, expire.isoformat()),
        )

    log_payment(call.from_user.id, "crypto", days, CRYPTO_PRICES.get(days, 0), "USDT")

    should_pay_ref_bonus = ref_id and not ref_bonus_paid

    if should_pay_ref_bonus:
        cursor.execute("SELECT expire_date FROM users WHERE user_id=?", (ref_id,))
        ref_user = cursor.fetchone()

        if ref_user:
            now = datetime.now()
            ref_expire_date = ref_user[0]
            base_expire = now

            if ref_expire_date:
                stored_expire = datetime.fromisoformat(ref_expire_date)
                if stored_expire > now:
                    base_expire = stored_expire

            new_expire = base_expire + timedelta(days=7)

            cursor.execute(
                "UPDATE users SET expire_date=?, refs_paid = refs_paid + 1 WHERE user_id=?",
                (new_expire.isoformat(), ref_id),
            )
            cursor.execute(
                "UPDATE users SET ref_bonus_paid=1 WHERE user_id=?",
                (call.from_user.id,),
            )

    conn.commit()

    if should_pay_ref_bonus and ref_user:
        await bot.send_message(ref_id, "🎉 Твой реферал оплатил! +7 дней к подписке")

    invite = await bot.create_chat_invite_link(
        chat_id=GROUP_ID,
        member_limit=1,
        expire_date=None,
        creates_join_request=False,
    )

    kb = InlineKeyboardMarkup().add(
        InlineKeyboardButton("Продлить подписку 🔁", callback_data="renew")
    )
    kb.add(InlineKeyboardButton("Реферальная ссылка 🎁", callback_data="ref_link"))

    await call.message.answer(
        f"Доступ активирован до {expire.date()}\n\n{invite.invite_link}",
        reply_markup=kb,
    )
    await call.message.answer(
        "⚠️ Ссылка одноразовая.\nПри передаче доступ будет заблокирован."
    )


@dp.callback_query_handler(lambda c: c.data == "back_main")
async def back_main(call: types.CallbackQuery):
    await call.message.delete()
    await call.answer()


@dp.callback_query_handler(lambda c: c.data == "reinvite")
async def reinvite(call: types.CallbackQuery):
    cursor.execute("SELECT expire_date FROM users WHERE user_id=?", (call.from_user.id,))
    row = cursor.fetchone()

    if not row:
        await call.message.answer("Нет активной подписки")
        return

    invite = await bot.create_chat_invite_link(
        chat_id=GROUP_ID,
        member_limit=1,
    )

    await call.message.answer(f"Новая ссылка:\n{invite.invite_link}")


@dp.callback_query_handler(lambda c: c.data == "back_plan")
async def back_plan(call: types.CallbackQuery):
    await call.message.delete()
    await call.answer()


@dp.callback_query_handler(lambda c: c.data == "plan_1")
async def plan_1(call: types.CallbackQuery):
    await call.answer()

    kb = InlineKeyboardMarkup(row_width=1)
    kb.add(
        InlineKeyboardButton("💳 Оплатить 1 день", callback_data="pay_1"),
        InlineKeyboardButton("⬅ Назад", callback_data="back_plan"),
    )

    await bot.send_message(
        call.from_user.id,
        "⭐ ТАРИФ: 1 ДЕНЬ\n\n"
        "Доступ к закрытому каналу на 24 часа.\n"
        "После оплаты доступ активируется автоматически.",
        reply_markup=kb,
    )


@dp.callback_query_handler(lambda c: c.data == "pay_1")
async def pay_1(call: types.CallbackQuery):
    wait = check_invoice_cooldown(call.from_user.id)
    if wait > 0:
        await call.answer(f"Подожди {wait} сек.", show_alert=True)
        return

    plan = PLANS["plan_1"]

    await bot.send_invoice(
        chat_id=call.message.chat.id,
        title=plan["title"],
        description="Доступ в закрытую группу",
        payload="plan_1",
        provider_token="",
        currency="XTR",
        prices=[types.LabeledPrice(label=plan["title"], amount=plan["amount"])],
        start_parameter="buy",
    )
    mark_invoice_created(call.from_user.id)
    await call.answer()


@dp.callback_query_handler(lambda c: c.data == "plan_7")
async def plan_7(call: types.CallbackQuery):
    await call.answer()

    kb = InlineKeyboardMarkup(row_width=1)
    kb.add(
        InlineKeyboardButton("💳 Оплатить 7 дней", callback_data="pay_7"),
        InlineKeyboardButton("⬅ Назад", callback_data="back_plan"),
    )

    await bot.send_message(
        call.from_user.id,
        "⭐ ТАРИФ: 7 ДНЕЙ\n\n"
        "Неделя доступа к закрытому каналу.\n"
        "Оптимальный вариант по цене/ценности.",
        reply_markup=kb,
    )


@dp.callback_query_handler(lambda c: c.data == "pay_7")
async def pay_7(call: types.CallbackQuery):
    wait = check_invoice_cooldown(call.from_user.id)
    if wait > 0:
        await call.answer(f"Подожди {wait} сек.", show_alert=True)
        return

    plan = PLANS["plan_7"]

    await bot.send_invoice(
        chat_id=call.message.chat.id,
        title=plan["title"],
        description="Доступ в закрытую группу",
        payload="plan_7",
        provider_token="",
        currency="XTR",
        prices=[types.LabeledPrice(label=plan["title"], amount=plan["amount"])],
        start_parameter="buy",
    )
    mark_invoice_created(call.from_user.id)
    await call.answer()


@dp.callback_query_handler(lambda c: c.data == "plan_30")
async def plan_30(call: types.CallbackQuery):
    await call.answer()

    kb = InlineKeyboardMarkup(row_width=1)
    kb.add(
        InlineKeyboardButton("💳 Оплатить 30 дней", callback_data="pay_30"),
        InlineKeyboardButton("⬅ Назад", callback_data="back_plan"),
    )

    await bot.send_message(
        call.from_user.id,
        "⭐ ТАРИФ: 30 ДНЕЙ\n\n"
        "Полный месяц доступа к закрытому каналу.\n"
        "Максимальная выгода и экономия.",
        reply_markup=kb,
    )


@dp.callback_query_handler(lambda c: c.data == "pay_30")
async def pay_30(call: types.CallbackQuery):
    wait = check_invoice_cooldown(call.from_user.id)
    if wait > 0:
        await call.answer(f"Подожди {wait} сек.", show_alert=True)
        return

    plan = PLANS["plan_30"]

    await bot.send_invoice(
        chat_id=call.message.chat.id,
        title=plan["title"],
        description="Доступ в закрытую группу",
        payload="plan_30",
        provider_token="",
        currency="XTR",
        prices=[types.LabeledPrice(label=plan["title"], amount=plan["amount"])],
        start_parameter="buy",
    )
    mark_invoice_created(call.from_user.id)
    await call.answer()


@dp.callback_query_handler(lambda c: c.data.startswith("plan_"))
async def plans(call: types.CallbackQuery):
    plan = PLANS[call.data]

    await bot.send_invoice(
        chat_id=call.message.chat.id,
        title=plan["title"],
        description="Доступ в закрытую группу",
        payload=call.data,
        provider_token="",
        currency="XTR",
        prices=[types.LabeledPrice(label=plan["title"], amount=plan["amount"])],
        start_parameter="buy",
    )
    await call.answer()


@dp.pre_checkout_query_handler(lambda q: True)
async def checkout(pre_checkout_q: types.PreCheckoutQuery):
    await bot.answer_pre_checkout_query(pre_checkout_q.id, ok=True)


@dp.message_handler(content_types=ContentType.SUCCESSFUL_PAYMENT)
async def success(message: types.Message):
    days = 1

    if "plan_7" in message.successful_payment.invoice_payload:
        days = 7
    elif "plan_30" in message.successful_payment.invoice_payload:
        days = 30

    expire = datetime.now() + timedelta(days=days)

    cursor.execute(
        """
        SELECT ref_by, ref_bonus_paid FROM users WHERE user_id=?
        """,
        (message.from_user.id,),
    )
    user_row = cursor.fetchone()

    if user_row:
        ref_id, ref_bonus_paid = user_row

        cursor.execute(
            """
            UPDATE users SET expire_date=?, notified=0 WHERE user_id=?
            """,
            (expire.isoformat(), message.from_user.id),
        )
    else:
        ref_id = None
        ref_bonus_paid = 0

        cursor.execute(
            """
            INSERT INTO users (user_id, expire_date, notified)
            VALUES (?, ?, 0)
            """,
            (message.from_user.id, expire.isoformat()),
        )

    log_payment(message.from_user.id, "stars", days, STARS_PRICES.get(days, 0), "XTR")

    should_pay_ref_bonus = ref_id and not ref_bonus_paid

    if should_pay_ref_bonus:
        cursor.execute("SELECT expire_date FROM users WHERE user_id=?", (ref_id,))
        ref_user = cursor.fetchone()

        if ref_user:
            now = datetime.now()
            ref_expire_date = ref_user[0]
            base_expire = now

            if ref_expire_date:
                stored_expire = datetime.fromisoformat(ref_expire_date)
                if stored_expire > now:
                    base_expire = stored_expire

            new_expire = base_expire + timedelta(days=7)

            cursor.execute(
                """
                UPDATE users SET expire_date=?, refs_paid = refs_paid + 1 WHERE user_id=?
                """,
                (new_expire.isoformat(), ref_id),
            )

            cursor.execute(
                """
                UPDATE users SET ref_bonus_paid=1 WHERE user_id=?
                """,
                (message.from_user.id,),
            )

    conn.commit()

    if should_pay_ref_bonus and ref_user:
        await bot.send_message(ref_id, "🎉 Твой реферал оплатил! +7 дней к подписке")

    invite = await bot.create_chat_invite_link(
        chat_id=GROUP_ID,
        member_limit=1,
        expire_date=None,
        creates_join_request=False,
    )

    kb = InlineKeyboardMarkup().add(
        InlineKeyboardButton("Продлить подписку 🔁", callback_data="renew")
    )
    kb.add(
        InlineKeyboardButton("Реферальная ссылка 🎁", callback_data="ref_link")
    )

    await message.answer(
        f"Доступ активирован до {expire.date()}\n\n{invite.invite_link}",
        reply_markup=kb,
    )
    await message.answer(
        "⚠️ Ссылка одноразовая.\n"
        "При передаче доступ будет заблокирован."
    )


@dp.chat_member_handler()
async def check_member(update: types.ChatMemberUpdated):
    user_id = update.from_user.id

    cursor.execute("SELECT expire_date FROM users WHERE user_id=?", (user_id,))
    row = cursor.fetchone()

    if not row:
        await bot.ban_chat_member(GROUP_ID, user_id)
        await bot.unban_chat_member(GROUP_ID, user_id)
        return


async def check_subscriptions():
    while True:
        now = datetime.now()

        cursor.execute("SELECT user_id, expire_date, notified FROM users")
        rows = cursor.fetchall()

        for user_id, expire_date, notified in rows:
            if not expire_date:
                continue

            try:
                expire_dt = datetime.fromisoformat(expire_date)
            except:
                continue

            time_left = expire_dt - now

            if time_left.total_seconds() < 0:
                try:
                    await bot.ban_chat_member(GROUP_ID, user_id)
                    await bot.unban_chat_member(GROUP_ID, user_id)

                    kb = InlineKeyboardMarkup(row_width=1)
                    kb.add(
                        InlineKeyboardButton("🔁 Продлить подписку", callback_data="renew"),
                    )

                    try:
                        await bot.send_message(
                            user_id,
                            "⏳ Твоя подписка на MistyBibi истекла.\n\n"
                            "Доступ к закрытому каналу закрыт.\n"
                            "Чтобы вернуться — продли подписку:",
                            reply_markup=kb,
                        )
                    except:
                        pass

                    cursor.execute("DELETE FROM users WHERE user_id=?", (user_id,))
                    conn.commit()
                except:
                    pass

            elif time_left.total_seconds() <= 86400 and not notified:
                kb = InlineKeyboardMarkup(row_width=1)
                kb.add(
                    InlineKeyboardButton("🔁 Продлить подписку", callback_data="renew"),
                )

                try:
                    await bot.send_message(
                        user_id,
                        "🔔 Напоминание\n\n"
                        "Твоя подписка на MistyBibi заканчивается менее чем через 24 часа.\n"
                        "Продли сейчас, чтобы не потерять доступ:",
                        reply_markup=kb,
                    )

                    cursor.execute(
                        "UPDATE users SET notified=1 WHERE user_id=?",
                        (user_id,),
                    )
                    conn.commit()
                except:
                    pass

        await asyncio.sleep(300)


async def check_crypto_payments():
    while True:
        cursor.execute("SELECT invoice_id, user_id, days FROM payments WHERE status='pending'")
        rows = cursor.fetchall()

        for invoice_id, user_id, days in rows:
            try:
                status = check_invoice(invoice_id)
            except CryptoPayError as e:
                logger.warning("background check_invoice failed: %s", e)
                continue
            except Exception as e:
                logger.exception("unexpected error in background check: %s", e)
                continue

            if status == "paid":
                expire = datetime.now() + timedelta(days=days)

                cursor.execute("""
                    INSERT OR REPLACE INTO users (user_id, expire_date, notified)
                    VALUES (?, ?, 0)
                """, (user_id, expire.isoformat()))

                cursor.execute("""
                    UPDATE payments SET status='paid' WHERE invoice_id=?
                """, (invoice_id,))

                log_payment(user_id, "crypto", days, CRYPTO_PRICES.get(days, 0), "USDT")

                conn.commit()

                invite = await bot.create_chat_invite_link(
                    chat_id=GROUP_ID,
                    member_limit=1,
                )

                await bot.send_message(
                    user_id,
                    f"Оплата прошла ✅\nДоступ до {expire.date()}\n{invite.invite_link}"
                )

        await asyncio.sleep(20)


async def on_startup(_):
    await bot.set_my_commands([
        types.BotCommand("start", "🚀 Запустить бота"),
        types.BotCommand("sub", "📅 Моя подписка"),
        types.BotCommand("ref", "🎁 Реферальная программа"),
        types.BotCommand("help", "ℹ️ Помощь и поддержка"),
    ])

    asyncio.create_task(check_subscriptions())
    asyncio.create_task(check_crypto_payments())
    asyncio.create_task(auto_backup())


@dp.message_handler(commands=["ref"])
async def ref_cmd(message: types.Message):
    bot_info = await bot.get_me()
    link = f"https://t.me/{bot_info.username}?start={message.from_user.id}"

    cursor.execute("SELECT refs_paid FROM users WHERE user_id=?", (message.from_user.id,))
    row = cursor.fetchone()
    count = row[0] if row else 0

    kb = InlineKeyboardMarkup(row_width=1)
    kb.add(InlineKeyboardButton("⬅ Назад", callback_data="back_plan"))

    await message.answer(
        "🎁 РЕФЕРАЛЬНАЯ ПРОГРАММА\n\n"
        f"🔗 Твоя ссылка:\n{link}\n\n"
        f"📊 Оплативших друзей: {count}\n"
        f"🎁 Бонус: +7 дней за каждого",
        reply_markup=kb,
    )


@dp.message_handler(commands=["help"])
async def help_cmd(message: types.Message):
    kb = InlineKeyboardMarkup(row_width=1)
    kb.add(
        InlineKeyboardButton("💬 Связаться с поддержкой", url="https://t.me/mistybibi"),
        InlineKeyboardButton("⬅ Назад", callback_data="back_plan"),
    )

    await message.answer(
        "ℹ️ ПОМОЩЬ\n\n"
        "Доступные команды:\n"
        "/start — главное меню\n"
        "/sub — статус твоей подписки\n"
        "/ref — реферальная программа\n"
        "/help — эта справка\n\n"
        "По вопросам оплаты и доступа — пиши в поддержку:",
        reply_markup=kb,
    )


@dp.message_handler(commands=["myid"])
async def myid_cmd(message: types.Message):
    await message.answer(f"🆔 Твой ID: `{message.from_user.id}`", parse_mode="Markdown")


@dp.message_handler(commands=["admin"])
async def admin_cmd(message: types.Message):
    if not is_admin(message.from_user.id):
        return

    text = (
        "🛠 АДМИН-ПАНЕЛЬ\n\n"
        "Доступные команды:\n\n"
        "/stats — статистика и выручка\n"
        "/give <user_id> <дни> — выдать доступ\n"
        "/revoke <user_id> — отозвать доступ\n"
        "/broadcast <текст> — рассылка всем подписчикам\n"
        "/users — список подписчиков"
    )
    await message.answer(text)


@dp.message_handler(commands=["stats"])
async def stats_cmd(message: types.Message):
    if not is_admin(message.from_user.id):
        return

    now = datetime.now()
    today = now.replace(hour=0, minute=0, second=0, microsecond=0)
    week_ago = now - timedelta(days=7)
    month_ago = now - timedelta(days=30)

    def revenue_since(method: str, currency: str, since: datetime) -> float:
        cursor.execute(
            "SELECT COALESCE(SUM(amount), 0), COUNT(*) FROM payments_log "
            "WHERE method=? AND currency=? AND created_at >= ?",
            (method, currency, since.isoformat()),
        )
        return cursor.fetchone()

    stars_today = revenue_since("stars", "XTR", today)
    stars_week = revenue_since("stars", "XTR", week_ago)
    stars_month = revenue_since("stars", "XTR", month_ago)
    stars_total = revenue_since("stars", "XTR", datetime(2000, 1, 1))

    crypto_today = revenue_since("crypto", "USDT", today)
    crypto_week = revenue_since("crypto", "USDT", week_ago)
    crypto_month = revenue_since("crypto", "USDT", month_ago)
    crypto_total = revenue_since("crypto", "USDT", datetime(2000, 1, 1))

    cursor.execute(
        "SELECT COUNT(*) FROM users WHERE expire_date IS NOT NULL AND expire_date > ?",
        (now.isoformat(),),
    )
    active_subs = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM users")
    total_users = cursor.fetchone()[0]

    cursor.execute(
        "SELECT days, COUNT(*) FROM payments_log GROUP BY days ORDER BY days"
    )
    by_plan = cursor.fetchall()

    text = (
        "📊 СТАТИСТИКА\n\n"
        f"👥 Пользователей в БД: {total_users}\n"
        f"✅ Активных подписок: {active_subs}\n\n"
        "⭐ TELEGRAM STARS:\n"
        f"Сегодня: {int(stars_today[0])} ⭐ ({stars_today[1]} опл.)\n"
        f"7 дней: {int(stars_week[0])} ⭐ ({stars_week[1]} опл.)\n"
        f"30 дней: {int(stars_month[0])} ⭐ ({stars_month[1]} опл.)\n"
        f"Всего: {int(stars_total[0])} ⭐ ({stars_total[1]} опл.)\n\n"
        "💰 CRYPTO (USDT):\n"
        f"Сегодня: {crypto_today[0]:.2f} ({crypto_today[1]} опл.)\n"
        f"7 дней: {crypto_week[0]:.2f} ({crypto_week[1]} опл.)\n"
        f"30 дней: {crypto_month[0]:.2f} ({crypto_month[1]} опл.)\n"
        f"Всего: {crypto_total[0]:.2f} ({crypto_total[1]} опл.)\n\n"
        "📦 ПРОДАЖИ ПО ТАРИФАМ:\n"
    )

    if by_plan:
        for days, cnt in by_plan:
            text += f"{days} дн.: {cnt} опл.\n"
    else:
        text += "пока пусто"

    await message.answer(text)


@dp.message_handler(commands=["give"])
async def give_cmd(message: types.Message):
    if not is_admin(message.from_user.id):
        return

    parts = message.get_args().split()

    if len(parts) != 2 or not parts[0].isdigit() or not parts[1].isdigit():
        await message.answer("Использование: /give <user_id> <дни>")
        return

    target_id = int(parts[0])
    days = int(parts[1])

    cursor.execute("SELECT expire_date FROM users WHERE user_id=?", (target_id,))
    row = cursor.fetchone()

    now = datetime.now()
    base = now

    if row and row[0]:
        try:
            stored = datetime.fromisoformat(row[0])
            if stored > now:
                base = stored
        except:
            pass

    new_expire = base + timedelta(days=days)

    if row:
        cursor.execute(
            "UPDATE users SET expire_date=?, notified=0 WHERE user_id=?",
            (new_expire.isoformat(), target_id),
        )
    else:
        cursor.execute(
            "INSERT INTO users (user_id, expire_date, notified) VALUES (?, ?, 0)",
            (target_id, new_expire.isoformat()),
        )

    conn.commit()

    try:
        invite = await bot.create_chat_invite_link(
            chat_id=GROUP_ID,
            member_limit=1,
        )

        await bot.send_message(
            target_id,
            f"🎁 Тебе выдан доступ на {days} дн.\n"
            f"Действует до: {new_expire.strftime('%d.%m.%Y %H:%M')}\n\n"
            f"{invite.invite_link}",
        )

        await message.answer(
            f"✅ Выдан доступ {target_id} на {days} дн.\n"
            f"До: {new_expire.strftime('%d.%m.%Y %H:%M')}"
        )
    except Exception as e:
        await message.answer(
            f"⚠️ Доступ записан в БД, но не удалось отправить ссылку:\n{e}"
        )


@dp.message_handler(commands=["revoke"])
async def revoke_cmd(message: types.Message):
    if not is_admin(message.from_user.id):
        return

    args = message.get_args().strip()

    if not args.isdigit():
        await message.answer("Использование: /revoke <user_id>")
        return

    target_id = int(args)

    try:
        await bot.ban_chat_member(GROUP_ID, target_id)
        await bot.unban_chat_member(GROUP_ID, target_id)
    except:
        pass

    cursor.execute("DELETE FROM users WHERE user_id=?", (target_id,))
    conn.commit()

    await message.answer(f"✅ Доступ для {target_id} отозван")


def make_backup_file() -> str:
    backup_path = f"backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"

    src = sqlite3.connect("users.db")
    dst = sqlite3.connect(backup_path)

    with dst:
        src.backup(dst)

    src.close()
    dst.close()

    return backup_path


async def send_backup_to_admin() -> bool:
    if not ADMIN_ID:
        return False

    path = make_backup_file()

    try:
        with open(path, "rb") as f:
            await bot.send_document(
                ADMIN_ID,
                types.InputFile(f, filename=path),
                caption=f"💾 Резервная копия БД\n{datetime.now().strftime('%d.%m.%Y %H:%M')}",
            )
        return True
    finally:
        try:
            os.remove(path)
        except:
            pass


async def auto_backup():
    while True:
        await asyncio.sleep(86400)
        try:
            await send_backup_to_admin()
        except Exception as e:
            logger.warning("auto backup failed: %s", e)


@dp.message_handler(commands=["backup"])
async def backup_cmd(message: types.Message):
    if not is_admin(message.from_user.id):
        return

    try:
        ok = await send_backup_to_admin()
        if not ok:
            await message.answer("⚠️ ADMIN_ID не настроен")
    except Exception as e:
        await message.answer(f"❌ Ошибка резервного копирования:\n{e}")


@dp.message_handler(commands=["broadcast"])
async def broadcast_cmd(message: types.Message):
    if not is_admin(message.from_user.id):
        return

    text = message.get_args()

    if not text:
        await message.answer("Использование: /broadcast <текст сообщения>")
        return

    cursor.execute("SELECT user_id FROM users")
    rows = cursor.fetchall()

    sent = 0
    failed = 0

    for (user_id,) in rows:
        try:
            await bot.send_message(user_id, text)
            sent += 1
            await asyncio.sleep(0.05)
        except:
            failed += 1

    await message.answer(f"📢 Рассылка завершена:\n✅ Доставлено: {sent}\n❌ Ошибок: {failed}")


@dp.message_handler(commands=["test"])
async def test(message: types.Message):
    await message.answer("бот жив")


@dp.message_handler(commands=["ping"])
async def ping(message: types.Message):
    await message.answer("бот жив")


@dp.message_handler()
async def debug(message: types.Message):
    await message.answer(f"CHAT ID: {message.chat.id}")



async def start_bot():
    try:
        # Эти строки ДОЛЖНЫ иметь отступ в 8 пробелов от края
        await dp.start_polling(bot)
    finally:
        # И эта тоже
        await bot.session.close()

if __name__ == '__main__':
    # Эта строка без отступа
    asyncio.run(start_bot())
