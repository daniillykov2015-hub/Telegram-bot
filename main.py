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
    "1": {"stars": 550, "crypto": 5},
    "7": {"stars": 770, "crypto": 7},
    "30": {"stars": 1100, "crypto": 10},
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
Администрация хранит информацию необходимый срок, применяет разумные меры защиты, но не гарантирует абсолютной безопасности. Пользователь самостоятельно риски передачи данных и принимает любые изменения в политике, продолжая использовать сервис.

1. Общие положения
 1.1. Настоящая Политика конфиденциальности (далее — «Политика») регулирует порядок обработки и защиты информации, которую Пользователь передаёт при использовании сервиса (далее — «Сервис»).
 1.2. Используя Сервис, Пользователь подтверждает своё согласие с условиями Политики. Если Пользователь не согласен с условиями — он обязан прекратить использование Сервиса.

2. Сбор информации
 2.1. Сервис может собирать следующие типы данных:
 идентификаторы аккаунта (логин, ID, никнейм и т.п.);
 техническую информацию (IP-адрес, данные о браузере, устройстве и операционной системе);
 историю взаимодействий с Сервисом.
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
2.2. Материалы могут включать информацию из открытых источников, авторские материалы Администрации, аналитические обзоры.
2.3. Пользователь понимает, что ценность Сервиса заключается в структуре, подаче и обработке информации, а не в уникальности отдельных данных.

3. Отказ от гарантий и ответственности
3.1. Сервис предоставляется на условиях «AS IS» («как есть»).
3.2. Администрация не гарантирует достижение результатов или бесперебойную работу.
3.3. Администрация не несёт ответственности за любые убытки, потерю данных или действия третьих лиц.

4. Законность использования
4.1. Пользователь обязуется не использовать Сервис в противоправных целях.
4.2. Ответственность за использование Сервиса полностью лежит на Пользователе.

5. Интеллектуальная собственность
5.1. Все материалы защищены авторским правом. Запрещено копирование, распространение и перепродажа без разрешения.

6. Ограничение доступа
6.1. Администрация вправе ограничить или прекратить доступ к Сервису в любое время.

7. Платежи и возвраты
7.1. Доступ предоставляется после оплаты.
7.2. Возврат средств не предусмотрен, кроме случаев, когда услуга не была оказана.
7.3. Запрещены chargeback без обращения в поддержку.

8. Конфиденциальность
8.1. Сервис собирает минимальную информацию. Полной безопасности в интернете не гарантируется.

9. Изменение условий
9.1. Условия могут изменяться. Использование = согласие.

10. Контакты
10.1. Поддержка через бота.
Пользователь подтверждает согласие с условиями."""

# ================== KEYBOARDS ==================
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
        [InlineKeyboardButton(text="1 день — 550 ⭐", callback_data="stars:1")],
        [InlineKeyboardButton(text="7 дней — 770 ⭐", callback_data="stars:7")],
        [InlineKeyboardButton(text="30 дней — 1100 ⭐", callback_data="stars:30")],
        [InlineKeyboardButton(text="⬅ Назад", callback_data="back")]
    ])
    await call.message.edit_text("⭐ Выберите тариф Stars:", reply_markup=kb)
    await call.answer()

@router.callback_query(F.data.startswith("stars:"))
async def stars_pay_directly(call: CallbackQuery):
    plan = call.data.split(":")[1]
    
    # Сразу отправляем инвойс без промежуточного окна "Нажмите оплатить"
    await bot.send_invoice(
        chat_id=call.message.chat.id,
        title="Подписка",
        description=f"Доступ на {plan} дней",
        payload=f"stars_{plan}",
        provider_token="",
        currency="XTR",
        prices=[LabeledPrice(label="Access", amount=PLANS[plan]["stars"])]
    )
    await call.answer()

# --- CRYPTO LOGIC ---

@router.callback_query(F.data == "crypto")
async def crypto_menu(call: CallbackQuery):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="1 день — 5$", callback_data="crypto:1")],
        [InlineKeyboardButton(text="7 дней — 7$", callback_data="crypto:7")],
        [InlineKeyboardButton(text="30 дней — 10$", callback_data="crypto:30")],
        [InlineKeyboardButton(text="⬅ Назад", callback_data="back")]
    ])
    await call.message.edit_text("💰 Выберите тариф Crypto (USDT):", reply_markup=kb)
    await call.answer()

@router.callback_query(F.data.startswith("crypto:"))
async def crypto_pay(call: CallbackQuery):
    plan = call.data.split(":")[1]
    
    async with aiohttp.ClientSession() as session:
        async with session.post(
            "https://pay.crypt.bot/api/createInvoice",
            headers={"Crypto-Pay-API-Token": CRYPTO_TOKEN},
            json={
                "asset": "USDT",
                "amount": str(PLANS[plan]["crypto"]),
                "description": f"{plan} days access"
            }
        ) as response:
            r = await response.json()

    if not r.get("ok"):
        await call.message.answer("❌ Ошибка создания счета в CryptoPay")
        return

    url = r["result"]["pay_url"]
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💰 Оплатить USDT", url=url)],
        [InlineKeyboardButton(text="⬅ Назад", callback_data="crypto")]
    ])

    await call.message.edit_text(f"💰 Оплата {plan} дней подписки через CryptoBot", reply_markup=kb)
    await call.answer()

# --- PAYMENT PROCESS ---

@router.pre_checkout_query()
async def pre_checkout(pre: PreCheckoutQuery):
    await pre.answer(ok=True)

@router.message(F.successful_payment)
async def success(message: Message):
    await message.answer("✅ Оплата прошла! Доступ активирован.")

# --- INFO & OTHER ---

@router.callback_query(F.data == "ref")
async def ref(call: CallbackQuery):
    text = (
        "👥 РЕФЕРАЛЬНАЯ СИСТЕМА\n\n"
        "Пригласи друга и получи +7 дней доступа\n\n"
        "УСЛОВИЯ:\n"
        "— у тебя должна быть активная подписка\n"
        "— друг должен оплатить подписку\n\n"
        "КАК ПОЛУЧИТЬ БОНУС:\n"
        "1. Отправь свою ссылку другу\n"
        "2. Он оплачивает доступ\n"
        "3. Ты получаешь +7 дней автоматически\n\n"
        f"Твоя ссылка:\nhttps://t.me/your_bot?start={call.from_user.id}"
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
