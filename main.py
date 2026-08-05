# main.py
import os
import asyncio
import logging
from io import BytesIO

from aiogram import Bot, Dispatcher, Router, F
from aiogram.types import Message, BufferedInputFile
from aiogram.filters import CommandStart, Command
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.context import FSMContext

import db
from parser import generate_mcpack

# ---------- Конфигурация ----------
TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = 123456789  # <-- замените на свой Telegram ID

if not TOKEN:
    raise RuntimeError("Укажите токен в переменной окружения BOT_TOKEN")

# ---------- Логирование ----------
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ---------- Инициализация ----------
bot = Bot(token=TOKEN)
dp = Dispatcher(storage=MemoryStorage())
router = Router()

# ---------- FSM для регистрации ----------
class Registration(StatesGroup):
    waiting_for_nickname = State()

# ---------- Вспомогательные функции ----------
async def show_profile(message: Message, user):
    await message.answer(
        f"📋 Ваш профиль:\n"
        f"🎮 Никнейм: {user['minecraft_nickname']}\n"
        f"🔋 Осталось генераций: {user['balance_generations']}"
    )

# ---------- Обработчики команд ----------
@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    user = await db.get_user(message.from_user.id)
    if user:
        await show_profile(message, user)
    else:
        await state.set_state(Registration.waiting_for_nickname)
        await message.answer(
            "👋 Добро пожаловать! Для использования бота укажите ваш никнейм в Minecraft Bedrock.\n"
            "Отправьте его одним сообщением (без пробелов)."
        )

@router.message(Command("profile"))
async def cmd_profile(message: Message):
    user = await db.get_user(message.from_user.id)
    if user:
        await show_profile(message, user)
    else:
        await message.answer("Вы ещё не зарегистрированы. Используйте /start.")

@router.message(Command("add"))
async def cmd_add(message: Message):
    if message.from_user.id != ADMIN_ID:
        return
    parts = message.text.split()
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
        await message.answer(f"Игрок с никнеймом '{nickname}' не найден.")
        return

    new_balance = await db.update_balance(user['telegram_id'], amount)
    await message.answer(
        f"✅ Баланс игрока {nickname} успешно пополнен на {amount}.\n"
        f"Текущий баланс: {new_balance}"
    )

# ---------- Приём никнейма (FSM) ----------
@router.message(Registration.waiting_for_nickname)
async def process_nickname(message: Message, state: FSMContext):
    nickname = message.text.strip()
    if not nickname or ' ' in nickname or len(nickname) > 16:
        await message.answer("❌ Никнейм не должен содержать пробелов и быть длиннее 16 символов. Попробуйте ещё раз.")
        return

    # Проверка, не занят ли никнейм другим пользователем (опционально)
    existing = await db.get_user_by_nickname(nickname)
    if existing:
        await message.answer("❌ Этот никнейм уже используется. Пожалуйста, выберите другой.")
        return

    await db.create_user(message.from_user.id, nickname)
    await state.clear()
    await message.answer(f"✅ Регистрация завершена! Ваш никнейм: {nickname}.\nВам начислено 3 стартовые генерации.")
    user = await db.get_user(message.from_user.id)
    await show_profile(message, user)

# ---------- Обработка файлов .mcstructure ----------
@router.message(F.document.file_name.endswith(".mcstructure"))
async def handle_mcstructure(message: Message):
    user = await db.get_user(message.from_user.id)
    if not user:
        await message.answer("Сначала зарегистрируйтесь — /start")
        return

    balance = user['balance_generations']
    if balance <= 0:
        await message.answer(
            "❌ У вас закончились генерации. Пополните баланс через администратора."
        )
        return

    # Скачиваем файл
    document = message.document
    file = await bot.get_file(document.file_id)
    file_bytes_io = BytesIO()
    await bot.download(file, destination=file_bytes_io)
    file_bytes_io.seek(0)
    file_bytes = file_bytes_io.read()

    # Пытаемся сгенерировать mcpack
    try:
        mcpack_bytes = generate_mcpack(file_bytes)
    except Exception as e:
        logger.exception("Ошибка генерации mcpack")
        await message.answer(
            "⚠️ Не удалось обработать файл. Возможно, он повреждён или имеет неверный формат."
        )
        return

    # Если успешно – списываем генерацию
    new_balance = await db.update_balance(user['telegram_id'], -1)

    # Отправляем файл пользователю
    filename = document.file_name.rsplit('.', 1)[0] + '.mcpack'
    input_file = BufferedInputFile(mcpack_bytes, filename=filename)
    try:
        await message.answer_document(
            input_file,
            caption=f"✅ Голограмма готова! Списана 1 генерация.\nВаш новый баланс: {new_balance}"
        )
    except Exception as e:
        # Возвращаем списанную генерацию
        await db.update_balance(user['telegram_id'], +1)
        logger.exception("Ошибка отправки файла")
        await message.answer("⚠️ Не удалось отправить файл, генерация возвращена. Попробуйте ещё раз.")
        return

# ---------- Запуск ----------
async def main():
    await db.init_db()
    dp.include_router(router)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
