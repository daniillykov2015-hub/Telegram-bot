import asyncio
from aiogram import Bot, Dispatcher
from aiogram.types import Message
from aiogram.filters import Command

TOKEN = "ТВОЙ_ТОКЕН"
ADMIN_ID = 123456789  # сюда вставь свой ID

bot = Bot(token=TOKEN)
dp = Dispatcher()


@dp.message(Command("start"))
async def start_handler(message: Message):
    await message.answer("Бот запущен 🚀")


@dp.message()
async def echo(message: Message):
    await message.answer(f"Ты написал: {message.text}")


async def main():
    print("Бот запущен...")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
