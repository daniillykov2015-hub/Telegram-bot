import asyncio
import logging
import os

from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command

TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))

logging.basicConfig(level=logging.INFO)

bot = Bot(token=TOKEN)
dp = Dispatcher()


@dp.message(Command("start"))
async def start(message: types.Message):
    await message.answer("Бот запущен и работает ✅")


@dp.message(Command("id"))
async def get_id(message: types.Message):
    await message.answer(f"Твой ID: {message.from_user.id}")


@dp.message(Command("admin"))
async def admin_only(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        await message.answer("Нет доступа ❌")
        return

    await message.answer("Админ панель активна 🔥")


async def main():
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
