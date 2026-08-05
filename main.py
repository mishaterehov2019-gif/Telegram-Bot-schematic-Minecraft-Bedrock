import asyncio
import logging
import os
from io import BytesIO

from aiogram import Bot, Dispatcher, Router, F
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import Message, BufferedInputFile

import db
from parser import generate_mcpack

# ---------- Настройки ----------
TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = 123456789          # ← замените на свой Telegram ID

if not TOKEN:
    raise RuntimeError("Не задан BOT_TOKEN. Укажите его в переменной окружения или прямо в коде.")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ---------- Инициализация ----------
bot = Bot(token=TOKEN)
dp = Dispatcher(storage=MemoryStorage())
router = Router()

# ---------- FSM ----------
class RegForm(StatesGroup):
    waiting_for_nickname = State()

# ---------- Утилита профиля ----------
async def show_profile(message: Message, user):
    await message.answer(
        f"📋 Ваш профиль:\n"
        f"🎮 Никнейм: {user['minecraft_nickname']}\n"
        f"🔋 Осталось генераций: {user['balance_generations']}"
    )

# ---------- Команда /start ----------
@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    user = await db.get_user(message.from_user.id)
    if user:
        await state.clear()  # на случай, если осталось незавершённое состояние
        await show_profile(message, user)
    else:
        await state.set_state(RegForm.waiting_for_nickname)
        await message.answer(
            "👋 Добро пожаловать! Для использования бота введите ваш никнейм в Minecraft Bedrock.\n"
            "Используйте только буквы, цифры и подчёркивания, без пробелов (до 16 символов)."
        )

# ---------- Команда /profile ----------
@router.message(Command("profile"))
async def cmd_profile(message: Message):
    user = await db.get_user(message.from_user.id)
    if user:
        await show_profile(message, user)
    else:
        await message.answer("Вы ещё не зарегистрированы. Напишите /start")

# ---------- Команда администратора /add ----------
@router.message(Command("add"))
async def cmd_add(message: Message):
    if message.from_user.id != ADMIN_ID:
        return  # тихо игнорируем
    parts = message.text.strip().split()
    if len(parts) != 3:
        await message.answer("Использование: /add <никнейм> <количество>")
        return
    _, nickname, amount_str = parts
    try:
        amount = int(amount_str)
    except ValueError:
        await message.answer("Количество должно быть целым числом.")
        return
    user = await db.get_user_by_nickname(nickname)
    if not user:
        await message.answer(f"Игрок с никнеймом '{nickname}' не найден в базе.")
        return
    new_balance = await db.update_balance(user['telegram_id'], amount)
    await message.answer(
        f"✅ Баланс игрока {nickname} пополнен на {amount}.\n"
        f"Текущий баланс: {new_balance}"
    )

# ---------- Приём никнейма (FSM) ----------
@router.message(RegForm.waiting_for_nickname)
async def process_nickname(message: Message, state: FSMContext):
    nick = message.text.strip()
    if not (1 <= len(nick) <= 16) or ' ' in nick:
        await message.answer("❌ Никнейм должен быть от 1 до 16 символов и без пробелов.")
        return
    # Проверка уникальности никнейма
    existing = await db.get_user_by_nickname(nick)
    if existing:
        await message.answer("❌ Этот никнейм уже используется другим пользователем. Придумайте другой.")
        return
    try:
        await db.create_user(message.from_user.id, nick)
    except Exception:
        # Если другой процесс уже вставил запись – аккуратно обработаем
        await message.answer("⚠️ Ошибка базы данных. Попробуйте другой никнейм.")
        return

    await state.clear()
    await message.answer(f"✅ Регистрация завершена! Ваш никнейм: {nick}.\nВам начислено 3 стартовые генерации.")
    user = await db.get_user(message.from_user.id)
    await show_profile(message, user)

# ---------- Обработка файлов .mcstructure ----------
@router.message(F.document.file_name.endswith(".mcstructure"))
async def handle_mcstructure(message: Message):
    user = await db.get_user(message.from_user.id)
    if not user:
        await message.answer("⛔ Сначала зарегистрируйтесь через /start")
        return
    if user['balance_generations'] <= 0:
        await message.answer("❌ У вас не осталось генераций. Обратитесь к администратору.")
        return

    # Скачиваем файл
    document = message.document
    file = await bot.get_file(document.file_id)
    file_bytes_io = BytesIO()
    await bot.download(file, destination=file_bytes_io)
    file_bytes_io.seek(0)
    file_bytes = file_bytes_io.read()

    # Генерация .mcpack
    try:
        mcpack_bytes = generate_mcpack(file_bytes)
    except Exception as e:
        logger.exception("Ошибка генерации mcpack")
        await message.answer(
            "⚠️ Не удалось обработать файл. Убедитесь, что это корректный .mcstructure из Minecraft Bedrock."
        )
        return

    # Списываем генерацию
    new_balance = await db.update_balance(user['telegram_id'], -1)

    # Отправляем результат
    original_name = document.file_name
    out_filename = original_name.rsplit('.', 1)[0] + '.mcpack'
    try:
        await message.answer_document(
            BufferedInputFile(mcpack_bytes, filename=out_filename),
            caption=f"✅ Голограмма готова! Списана 1 генерация.\nВаш баланс: {new_balance}"
        )
    except Exception:
        # Возвращаем генерацию при ошибке отправки
        await db.update_balance(user['telegram_id'], +1)
        logger.exception("Ошибка отправки файла")
        await message.answer("⚠️ Не удалось отправить файл, генерация возвращена. Попробуйте позже.")

# ---------- Точка входа ----------
async def main():
    await db.init_db()
    dp.include_router(router)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
