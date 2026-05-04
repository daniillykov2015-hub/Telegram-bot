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
    ChatMemberUpdated
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

try:
    CHANNEL_ID = int(CHANNEL_ID)
except ValueError:
    pass

DB_NAME = "users.db"

bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
dp = Dispatcher(storage=MemoryStorage())
router = Router()

http_session = None

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

# ================== TEXTS ==================
TEXTS = {
    "ru": {
        "main": "👋 Привет, я Ева.\n\nЭто мой закрытый уголок, куда я пускаю не всех.\n\nЗдесь ты увидишь то, что обычно остаётся за кадром.\n\nВыбери способ входа 👇",
        "buttons": {
            "card": "💳 Карта / СБП (₽)",
            "stars": "⭐ Stars",
            "crypto": "💰 Crypto ($)",
            "ref": "👥 Реферальная система",
            "support": "💬 Поддержка",
            "info": "ℹ️ Информация",
            "back": "⬅ Назад",
            "pay": "💸 Оплатить"
        },
        "choose_stars": "⭐ Выберите период подписки:",
        "choose_card": "💳 Выберите тариф:",
        "check_details": "<b>Проверьте детали платежа:</b>\n\n📦 Тариф: {plan_name}\n🗓 Срок: {plan_name}\n💳 Способ: {method}\n💰 К оплате: {amount}",
        "prepare_pay": "⏳ <b>Готовим платёж...</b>\n\nПодождите пару секунд",
        "pay_card_text": "💳 <b>Оплата {plan_name}</b>\n\n💰 Сумма: <b>{amount} ₽</b>\n\n👇 Нажмите кнопку ниже для оплаты",
        "error_service": "❌ Сервис временно недоступен",
        "error_payment": "❌ Ошибка создания платежа",
        "error_not_found": "❌ Тариф не найден",
        "access_granted": "✅ Доступ активирован!\n\n⏳ {days} дней с момента входа",
        "payment_success": "✅ Оплата прошла успешно! Доступ продлен.",
        "ref_text": "👥 <b>Реферальная система</b>\n\nПриглашай друзей и получай +7 дней за каждого!\n\n🔗 Твоя ссылка: <code>{ref_link}</code>\n\n📊 Приглашено: {ref_count}\n🎁 Получено бонусных дней: {bonus_days}"
    },
    "en": {
        "main": "👋 Hey, I'm Eva.\n\nThis is my private space — not everyone gets in.\n\nHere you’ll see what usually stays behind the scenes.\n\nChoose how you want to get access 👇",
        "buttons": {
            "card": "💳 Card / SBP (₽)",
            "stars": "⭐ Stars",
            "crypto": "💰 Crypto ($)",
            "ref": "👥 Referral system",
            "support": "💬 Support",
            "info": "ℹ️ Info",
            "back": "⬅ Back",
            "pay": "💸 Pay"
        },
        "choose_stars": "⭐ Choose a subscription period:",
        "choose_card": "💳 Choose a plan:",
        "check_details": "<b>Check payment details:</b>\n\n📦 Plan: {plan_name}\n🗓 Duration: {plan_name}\n💳 Method: {method}\n💰 Amount: {amount}",
        "prepare_pay": "⏳ <b>Preparing payment...</b>\n\nPlease wait a few seconds",
        "pay_card_text": "💳 <b>Payment for {plan_name}</b>\n\n💰 Amount: <b>{amount} ₽</b>\n\n👇 Click the button below to pay",
        "error_service": "❌ Service temporarily unavailable",
        "error_payment": "❌ Error creating payment",
        "error_not_found": "❌ Plan not found",
        "access_granted": "✅ Access granted!\n\n⏳ {days} days from the moment of entry",
        "payment_success": "✅ Payment successful! Access extended.",
        "ref_text": "👥 <b>Referral System</b>\n\nInvite friends and get +7 days for each!\n\n🔗 Your link: <code>{ref_link}</code>\n\n📊 Invited: {ref_count}\n🎁 Bonus days received: {bonus_days}"
    },
    "de": {
        "main": "👋 Hi, ich bin Eva.\n\nDas ist mein privater Raum — nicht jeder kommt hier rein.\n\nHier siehst du Dinge, die sonst verborgen bleiben.\n\nWähle deinen Zugang 👇",
        "buttons": {
            "card": "💳 Karte / SBP (₽)",
            "stars": "⭐ Stars",
            "crypto": "💰 Krypto ($)",
            "ref": "👥 Empfehlungssystem",
            "support": "💬 Support",
            "info": "ℹ️ Info",
            "back": "⬅ Zurück",
            "pay": "💸 Bezahlen"
        },
        "choose_stars": "⭐ Wähle einen Abo-Zeitraum:",
        "choose_card": "💳 Wähle einen Tarif:",
        "check_details": "<b>Zahlungsdetails prüfen:</b>\n\n📦 Tarif: {plan_name}\n🗓 Dauer: {plan_name}\n💳 Methode: {method}\n💰 Betrag: {amount}",
        "prepare_pay": "⏳ <b>Zahlung wird vorbereitet...</b>\n\nBitte warte ein paar Sekunden",
        "pay_card_text": "💳 <b>Zahlung für {plan_name}</b>\n\n💰 Betrag: <b>{amount} ₽</b>\n\n👇 Klicke unten, um zu bezahlen",
        "error_service": "❌ Service vorübergehend nicht verfügbar",
        "error_payment": "❌ Fehler bei der Zahlungserstellung",
        "error_not_found": "❌ Tarif nicht gefunden",
        "access_granted": "✅ Zugang gewährt!\n\n⏳ {days} Tage ab Eintritt",
        "payment_success": "✅ Zahlung erfolgreich! Zugang verlängert.",
        "ref_text": "👥 <b>Empfehlungssystem</b>\n\nLade Freunde ein und erhalte +7 Tage für jeden!\n\n🔗 Dein Link: <code>{ref_link}</code>\n\n📊 Eingeladen: {ref_count}\n🎁 Bonustage erhalten: {bonus_days}"
    },
    "es": {
        "main": "👋 Hola, soy Eva.\n\nEste es mi espacio privado — no todos entran aquí.\n\nAquí verás lo que normalmente no se muestra.\n\nElige cómo quieres entrar 👇",
        "buttons": {
            "card": "💳 Tarjeta / SBP (₽)",
            "stars": "⭐ Stars",
            "crypto": "💰 Cripto ($)",
            "ref": "👥 Referidos",
            "support": "💬 Soporte",
            "info": "ℹ️ Información",
            "back": "⬅ Atrás",
            "pay": "💸 Pagar"
        },
        "choose_stars": "⭐ Elige un período de suscripción:",
        "choose_card": "💳 Elige un plan:",
        "check_details": "<b>Comprueba los detalles de pago:</b>\n\n📦 Plan: {plan_name}\n🗓 Duración: {plan_name}\n💳 Método: {method}\n💰 A pagar: {amount}",
        "prepare_pay": "⏳ <b>Preparando el pago...</b>\n\nEspera unos segundos",
        "pay_card_text": "💳 <b>Pago de {plan_name}</b>\n\n💰 Cantidad: <b>{amount} ₽</b>\n\n👇 Haz clic abajo para pagar",
        "error_service": "❌ Servicio temporalmente no disponible",
        "error_payment": "❌ Error al crear el pago",
        "error_not_found": "❌ Plan no encontrado",
        "access_granted": "✅ ¡Acceso concedido!\n\n⏳ {days} días desde el momento de entrada",
        "payment_success": "✅ ¡Pago exitoso! Acceso extendido.",
        "ref_text": "👥 <b>Sistema de Referidos</b>\n\n¡Invita a amigos y obtén +7 días por cada uno!\n\n🔗 Tu enlace: <code>{ref_link}</code>\n\n📊 Invitados: {ref_count}\n🎁 Días de bonificación recibidos: {bonus_days}"
    },
    "fr": {
        "main": "👋 Salut, je suis Eva.\n\nC’est mon espace privé — tout le monde n’y a pas accès.\n\nIci, tu verras ce qui reste normalement hors caméra.\n\nChoisis ton accès 👇",
        "buttons": {
            "card": "💳 Carte / SBP (₽)",
            "stars": "⭐ Stars",
            "crypto": "💰 Crypto ($)",
            "ref": "👥 Parrainage",
            "support": "💬 Support",
            "info": "ℹ️ Info",
            "back": "⬅ Retour",
            "pay": "💸 Payer"
        },
        "choose_stars": "⭐ Choisissez une période d'abonnement :",
        "choose_card": "💳 Choisissez un forfait :",
        "check_details": "<b>Vérifiez les détails du paiement :</b>\n\n📦 Forfait : {plan_name}\n🗓 Durée : {plan_name}\n💳 Méthode : {method}\n💰 Montant : {amount}",
        "prepare_pay": "⏳ <b>Préparation du paiement...</b>\n\nVeuillez patienter quelques secondes",
        "pay_card_text": "💳 <b>Paiement pour {plan_name}</b>\n\n💰 Montant : <b>{amount} ₽</b>\n\n👇 Cliquez sur le bouton ci-dessous pour payer",
        "error_service": "❌ Service temporairement indisponible",
        "error_payment": "❌ Erreur de création de paiement",
        "error_not_found": "❌ Forfait introuvable",
        "access_granted": "✅ Accès accordé !\n\n⏳ {days} jours à partir de l'entrée",
        "payment_success": "✅ Paiement réussi ! Accès prolongé.",
        "ref_text": "👥 <b>Système de Parrainage</b>\n\nInvitez des amis et obtenez +7 jours pour chacun !\n\n🔗 Votre lien : <code>{ref_link}</code>\n\n📊 Invités : {ref_count}\n🎁 Jours de bonus reçus : {bonus_days}"
    }
}

PRIVACY_TEXT = """Политика конфиденциальности...""" # Сократил в ответе, в твоем коде оставь как было
TERMS_TEXT = """Пользовательское соглашение..."""   # Сократил в ответе, в твоем коде оставь как было

# ================== ТАРИФЫ ==================
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

        try:
            await db.execute("ALTER TABLE users ADD COLUMN lang TEXT DEFAULT 'ru'")
        except aiosqlite.OperationalError:
            pass

        await db.commit()

        # CRYPTO
        await db.execute("""
        CREATE TABLE IF NOT EXISTS crypto_invoices (
            invoice_id TEXT PRIMARY KEY,
            user_id INTEGER,
            plan_id TEXT,
            status TEXT DEFAULT 'pending'
        )
        """)

        # CARD / SBP (Platega)
        await db.execute("""
        CREATE TABLE IF NOT EXISTS card_invoices (
            payload TEXT PRIMARY KEY,
            user_id INTEGER,
            plan_id TEXT,
            status TEXT DEFAULT 'pending'
        )
        """)

        # invite links
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
                        lang = await get_lang(ref_id)
                        # Минимальный бонус текст, можно тоже вынести в TEXTS
                        await bot.send_message(ref_id, "💎 <b>Бонус начислен!</b>\n\nДруг оплатил подписку — тебе +7 дней 🔥")
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

    lang = row[0] if row and row[0] else "en"
    if lang not in TEXTS:
        lang = "en"
    return lang

# ================== KEYBOARDS & INVITE ==================
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
        if row and row[0] and row[1]:
            try:
                exp = datetime.fromisoformat(row[1]).replace(tzinfo=timezone.utc)
                if exp > now:
                    return row[0]
            except Exception:
                pass

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
        TEXTS[lang]["choose_stars"],
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
        await call.answer(TEXTS[lang]["error_not_found"], show_alert=True)
        return

    invoice_link = await bot.create_invoice_link(
        title="Subscription",
        description=f"Access for {plan['name']}",
        payload=f"stars_{plan_id}",
        provider_token="",
        currency="XTR",
        prices=[LabeledPrice(label="Stars", amount=plan["stars"])]
    )

    text = TEXTS[lang]["check_details"].format(
        plan_name=plan['name'],
        method="⭐ Stars",
        amount=f"{plan['stars']} ⭐"
    )

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=t["pay"], url=invoice_link)],
        [InlineKeyboardButton(text=t["back"], callback_data="stars")]
    ])

    await call.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    await call.answer()

# Обязательные хэндлеры для работы Telegram Stars
@router.pre_checkout_query()
async def process_pre_checkout_query(pre_checkout_query: PreCheckoutQuery):
    await pre_checkout_query.answer(ok=True)

@router.message(F.successful_payment)
async def process_successful_payment(message: Message):
    payload = message.successful_payment.invoice_payload
    if payload.startswith("stars_"):
        plan_id = payload.split("_")[1]
        plan = PLANS.get(plan_id)
        if plan:
            # Начисляем дни
            await extend_user(message.from_user.id, plan["days"])
            lang = await get_lang(message.from_user.id)
            await message.answer(TEXTS[lang]["payment_success"])
            await notify_admin(message.from_user.id, plan["name"], "Stars")

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
        TEXTS[lang]["choose_card"],
        reply_markup=kb
    )
    await call.answer()

# ---------- START ----------
@router.message(CommandStart())
async def start(message: Message):
    user_id = message.from_user.id
    
    # Обработка реферальной ссылки
    referrer_id = None
    if " " in message.text:
        try:
            referrer_id = int(message.text.split(" ")[1])
            if referrer_id == user_id:
                referrer_id = None
        except:
            pass

    async with aiosqlite.connect(DB_NAME) as db:
        if referrer_id:
            await db.execute(
                "INSERT OR IGNORE INTO users (user_id, referrer) VALUES (?, ?)",
                (user_id, referrer_id)
            )
        else:
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
                lang = await get_lang(user_id)
                msg_text = TEXTS[lang]["access_granted"].format(days=days)
                await bot.send_message(user_id, msg_text)
            except:
                pass

    except Exception as e:
        logging.error(f"chat_member error: {e}")

# --- PLATEGA ---
@router.callback_query(F.data.startswith("card_confirm:"))
async def card_confirm(call: CallbackQuery):
    lang = await get_lang(call.from_user.id)
    t_btn = TEXTS[lang]["buttons"]
    
    plan_id = call.data.split(":")[1]
    plan = PLANS.get(plan_id)

    if not plan:
        await call.answer(TEXTS[lang]["error_not_found"], show_alert=True)
        return

    if http_session is None:
        await call.message.answer(TEXTS[lang]["error_service"])
        await call.answer()
        return

    try:
        transaction_id = None
        pay_url = None

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
            if not pay_url:
                async with aiosqlite.connect(DB_NAME) as db:
                    await db.execute(
                        "UPDATE card_invoices SET status='expired' WHERE payload=?",
                        (transaction_id,)
                    )
                    await db.commit()
                transaction_id = None
                pay_url = None

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
                    await call.message.answer(TEXTS[lang]["error_service"])
                    return

            transaction_id = data.get("transactionId")
            pay_url = data.get("redirect")

            if not transaction_id or not pay_url:
                await call.message.answer(f"❌ Platega API error:\n{raw_text}")
                return

            async with aiosqlite.connect(DB_NAME) as db:
                await db.execute(
                    """
                    INSERT INTO card_invoices (payload, user_id, plan_id, status)
                    VALUES (?, ?, ?, ?)
                    """,
                    (transaction_id, call.from_user.id, plan_id, "pending")
                )
                await db.commit()

        await call.answer()
        await call.message.edit_reply_markup(reply_markup=None)

        await call.message.edit_text(
            TEXTS[lang]["prepare_pay"],
            parse_mode="HTML"
        )

        pay_text = TEXTS[lang]["pay_card_text"].format(
            plan_name=plan['name'],
            amount=plan['rub']
        )
        
        await call.message.edit_text(
            pay_text,
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text=t_btn["pay"], url=pay_url)],
                [InlineKeyboardButton(text=t_btn["back"], callback_data="pay_card")]
            ]),
            parse_mode="HTML"
        )

    except Exception as e:
        logger.exception(f"PLATEGA ERROR: {e}")
        await call.message.answer(TEXTS[lang]["error_payment"])

    await call.answer()

# --- CRYPTO ---
@router.callback_query(F.data.startswith("crypto_confirm:"))
async def crypto_confirm(call: CallbackQuery):
    lang = await get_lang(call.from_user.id)
    t_btn = TEXTS[lang]["buttons"]
    
    plan_id = call.data.split(":")[1]
    plan = PLANS.get(plan_id)

    if not plan:
        await call.answer(TEXTS[lang]["error_not_found"], show_alert=True)
        return

    if http_session is None:
        await call.message.answer(TEXTS[lang]["error_service"])
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
            if response.status not in (200, 201):
                await call.message.answer(TEXTS[lang]["error_service"])
                return

            try:
                data = await response.json()
            except Exception:
                await call.message.answer(TEXTS[lang]["error_service"])
                return

        if not data.get("ok"):
            await call.message.answer(TEXTS[lang]["error_payment"])
            return

        result = data["result"]
        pay_url = result.get("pay_url")
        invoice_id = str(result.get("invoice_id"))

        if not pay_url or not invoice_id:
            await call.message.answer(TEXTS[lang]["error_payment"])
            return

        async with aiosqlite.connect(DB_NAME) as db:
            await db.execute(
                """
                INSERT OR IGNORE INTO crypto_invoices (invoice_id, user_id, plan_id)
                VALUES (?, ?, ?)
                """,
                (invoice_id, call.from_user.id, plan_id)
            )
            await db.commit()

        text = TEXTS[lang]["check_details"].format(
            plan_name=plan['name'],
            method="💰 CryptoBot (USDT)",
            amount=f"{plan['crypto']} $"
        )

        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=t_btn["pay"], url=pay_url)],
            [InlineKeyboardButton(text=t_btn["back"], callback_data="crypto")]
        ])

        await call.message.edit_text(text, reply_markup=kb, parse_mode="HTML")

    except Exception as e:
        logger.error(f"Crypto createInvoice error: {e}")
        await call.message.answer(TEXTS[lang]["error_payment"])

    await call.answer()

# --- REFERRAL ---
@router.callback_query(F.data == "ref")
async def ref(call: CallbackQuery):
    user_id = call.from_user.id
    user_data = await get_user(user_id)
    lang = await get_lang(user_id)
    t = TEXTS[lang]["ref_text"]
    t_btn = TEXTS[lang]["buttons"]

    if not user_data:
        await call.answer(TEXTS[lang]["error_service"], show_alert=True)
        return

    ref_count = user_data[3]
    bonus_days = user_data[4]
    
    bot_info = await bot.me()
    ref_link = f"https://t.me/{bot_info.username}?start={user_id}"

    text = t.format(
        ref_link=ref_link,
        ref_count=ref_count,
        bonus_days=bonus_days
    )

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=t_btn["back"], callback_data="back")]
    ])

    await call.message.edit_text(text, reply_markup=kb, parse_mode="HTML", disable_web_page_preview=True)
    await call.answer()


# ================== STARTUP & SHUTDOWN ==================
@dp.startup()
async def on_startup():
    global http_session
    http_session = aiohttp.ClientSession()
    await init_db()
    logger.info("Bot started, DB initialized, HTTP session created.")

@dp.shutdown()
async def on_shutdown():
    if http_session:
        await http_session.close()
    logger.info("Bot stopped, HTTP session closed.")

# ================== RUNNER ==================
async def main():
    dp.include_router(router)
    # Удаляем вебхуки, если они были, чтобы пуллинг работал
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
