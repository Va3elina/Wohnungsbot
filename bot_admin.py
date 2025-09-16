# -*- coding: utf-8 -*-
import sqlite3
import pandas as pd
import asyncio
import os
from aiogram import Bot, Dispatcher, Router
from aiogram.types import Message, BufferedInputFile
from aiogram.enums import ParseMode
from aiogram.filters import Command
from aiogram.client.default import DefaultBotProperties
from dotenv import load_dotenv

# === Загрузка .env ===
load_dotenv()

ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))
ADMIN_TOKEN = os.getenv("ADMIN_TOKEN")

# Инициализация бота с поддержкой ParseMode
bot = Bot(token=ADMIN_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()
router = Router()
dp.include_router(router)

# 🔎 Проверка, является ли пользователь админом
def is_admin(user_id: int) -> bool:
    return user_id == ADMIN_ID

# 📊 Функция экспорта таблицы из SQLite в Excel
def export_table_to_excel(table_name: str) -> str:
    conn = sqlite3.connect("seen_ids.db")
    df = pd.read_sql_query(f"SELECT * FROM {table_name}", conn)
    filepath = f"{table_name}.xlsx"
    df.to_excel(filepath, index=False)
    conn.close()
    return filepath

# 🔘 /start
@router.message(Command("start"))
async def start(message: Message):
    if not is_admin(message.from_user.id):
        return
    await message.answer(
        "👋 Админ-бот запущен. Доступные команды:\n"
        "/export_users — выгрузить таблицу users\n"
        "/export_listings — выгрузить таблицу listings\n"
        "/set_sub <user_id> <YYYY-MM-DD> — выдать подписку вручную"
    )

# 🔘 /export_users
@router.message(Command("export_users"))
async def export_users(message: Message):
    if not is_admin(message.from_user.id):
        return
    path = export_table_to_excel("users")
    with open(path, "rb") as file:
        content = file.read()
        await message.answer_document(BufferedInputFile(content, filename=path))

# 🔘 /export_listings
@router.message(Command("export_listings"))
async def export_listings(message: Message):
    if not is_admin(message.from_user.id):
        return
    path = export_table_to_excel("listings")
    with open(path, "rb") as file:
        content = file.read()
        await message.answer_document(BufferedInputFile(content, filename=path))

# 🔘 /set_sub <user_id> <YYYY-MM-DD>
@router.message(Command("set_sub"))
async def set_subscription(message: Message):
    if not is_admin(message.from_user.id):
        return
    try:
        _, user_id, date_str = message.text.strip().split()
        conn = sqlite3.connect("seen_ids.db")
        cursor = conn.cursor()
        cursor.execute("UPDATE users SET subscribed_until = ? WHERE user_id = ?", (date_str, user_id))
        conn.commit()
        conn.close()
        await message.answer(f"✅ Подписка пользователю {user_id} установлена до {date_str}")
    except Exception as e:
        await message.answer(f"❌ Ошибка: {e}\nФормат: /set_sub <user_id> <YYYY-MM-DD>")

# 🚀 Запуск бота
async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
