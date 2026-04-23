import asyncio
import logging
import os
import aiohttp

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
CRYPTO_TOKEN = os.getenv("CRYPTO_TOKEN")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
router = Router()
dp.include_router(router)

# ================== PLANS ==================
PLANS = {
    "1": {"stars": 550, "crypto": 5, "name": "1 день"},
    "7": {"stars": 770, "crypto": 7, "name": "7 дней"},
    "30": {"stars": 1100, "crypto": 10, "name": "30 дней"},
}

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

# ================== MENU ==================
def menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="⭐ Stars", callback_data="stars"),
            InlineKeyboardButton(text="💰 Crypto", callback_data="crypto"),
        ],
        [InlineKeyboardButton(text="👥 Реферальная система", callback_data="ref")],
        [InlineKeyboardButton(text="ℹ️ Информация", callback_data="info")]
    ])

# ================== HANDLERS ==================

@router.message(CommandStart())
async def start(message: Message):
    await message.answer(MAIN_TEXT, reply_markup=menu())

@router.callback_query(F.data == "back")
async def back(call: CallbackQuery):
    await call.message.edit_text(MAIN_TEXT, reply_markup=menu())
    await call.answer()

# --- STARS LOGIC ---

@router.callback_query(F.data == "stars")
async def stars_menu(call: CallbackQuery):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="1 день — 550 ⭐", callback_data="stars_confirm:1")],
        [InlineKeyboardButton(text="7 дней — 770 ⭐", callback_data="stars_confirm:7")],
        [InlineKeyboardButton(text="30 дней — 1100 ⭐", callback_data="stars_confirm:30")],
        [InlineKeyboardButton(text="⬅ Назад", callback_data="back")]
    ])
    await call.message.edit_text("⭐ Выберите период подписки Stars:", reply_markup=kb)
    await call.answer()

@router.callback_query(F.data.startswith("stars_confirm:"))
async def stars_confirm(call: CallbackQuery):
    plan_id = call.data.split(":")[1]
    plan = PLANS[plan_id]
    
    invoice_link = await bot.create_invoice_link(
        title="Подписка",
        description=f"Доступ в закрытый канал на {plan['name']}",
        payload=f"stars_{plan_id}",
        provider_token="", 
        currency="XTR",
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

# --- CRYPTO LOGIC (ВИЗУАЛ КАК В STARS) ---

@router.callback_query(F.data == "crypto")
async def crypto_menu(call: CallbackQuery):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="1 день — 5$", callback_data="crypto_confirm:1")],
        [InlineKeyboardButton(text="7 дней — 7$", callback_data="crypto_confirm:7")],
        [InlineKeyboardButton(text="30 дней — 10$", callback_data="crypto_confirm:30")],
        [InlineKeyboardButton(text="⬅ Назад", callback_data="back")]
    ])
    await call.message.edit_text("💰 Выберите тариф Crypto (USDT):", reply_markup=kb)
    await call.answer()

@router.callback_query(F.data.startswith("crypto_confirm:"))
async def crypto_confirm(call: CallbackQuery):
    plan_id = call.data.split(":")[1]
    plan = PLANS[plan_id]
    
    async with aiohttp.ClientSession() as session:
        async with session.post(
            "https://pay.crypt.bot/api/createInvoice",
            headers={"Crypto-Pay-API-Token": CRYPTO_TOKEN},
            json={
                "asset": "USDT",
                "amount": str(plan["crypto"]),
                "description": f"Subscription {plan['name']}"
            }
        ) as response:
            r = await response.json()

    if not r.get("ok"):
        await call.message.answer("❌ Ошибка CryptoPay")
        return

    pay_url = r["result"]["pay_url"]

    # Обновленный текст для Crypto (визуал 1-в-1 как Stars)
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

# --- CHECKOUT ---

@router.pre_checkout_query()
async def pre_checkout(pre: PreCheckoutQuery):
    await pre.answer(ok=True)

@router.message(F.successful_payment)
async def success(message: Message):
    await message.answer("✅ Оплата прошла! Доступ активирован.")

# --- OTHER ---

@router.callback_query(F.data == "ref")
async def ref(call: CallbackQuery):
    text = (
        "👥 РЕФЕРАЛЬНАЯ СИСТЕМА\n\n"
        "Пригласи друга и получи +7 дней доступа\n\n"
    👥 ПРИГЛАСИ ДРУГА — ПОЛУЧИ +7 ДНЕЙ!

Хочешь пользоваться закрытым каналом дольше и бесплатно? Участвуй в нашей реферальной программе!

Как это работает:

Копируй свою уникальную ссылку ниже.

Отправь её другу.

Как только твой друг оплатит любую подписку, тебе автоматически начислится 7 дней бесплатного доступа!

⚠️ Важное условие:
Бонус начисляется только в том случае, если на момент приглашения у тебя есть активная подписка.

Твоя ссылка для приглашения:
https://t.me/your_bot?start={user_id}
    )
    await call.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅ Назад", callback_data="back")]
    ]))
    await call.answer()

@router.callback_query(F.data == "info")
async def info(call: CallbackQuery):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📄 Политика конфиденциальности", callback_data="privacy")],
        [InlineKeyboardButton(text="📜 Пользовательское соглашение", callback_data="terms")],
        [InlineKeyboardButton(text="💬 Поддержка", url="https://t.me/mistybibi")],
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

# ================== MAIN ==================
async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
