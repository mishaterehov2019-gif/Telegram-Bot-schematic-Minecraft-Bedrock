import asyncio
import logging
import os
from typing import Optional

from aiogram import Bot, Dispatcher, Router, F
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import Message, FSInputFile
from aiogram.filters import Command, CommandObject

import db
import parser

# Константы
ADMIN_ID = 123456789  # ← замените на свой Telegram ID
BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise RuntimeError("Не задан BOT_TOKEN в переменных окружения")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Инициализация
bot = Bot(token=BOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)
router = Router()
dp.include_router(router)

# Состояния FSM
class Registration(StatesGroup):
    waiting_for_nickname = State()

# ----------------------------------------------------------------------
# Команды /start и /profile
# ----------------------------------------------------------------------
@router.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext):
    user_id = message.from_user.id
    exists = await db.user_exists(user_id)
    if not exists:
        # Новый пользователь – начинаем регистрацию
        await state.set_state(Registration.waiting_for_nickname)
        await message.answer(
            "Добро пожаловать! Для начала работы введите ваш никнейм в Minecraft."
        )
    else:
        # Уже зарегистрирован – показываем профиль
        user_data = await db.get_user(user_id)
        nick, balance = user_data
        await message.answer(
            f"Ваш профиль:\nНикнейм: {nick}\nБаланс генераций: {balance}"
        )

@router.message(Registration.waiting_for_nickname)
async def process_nickname(message: Message, state: FSMContext):
    nick = message.text.strip()
    if not nick or len(nick) > 50:
        await message.answer("Некорректный никнейм. Попробуйте ещё раз.")
        return
    user_id = message.from_user.id
    # Добавляем в БД со стартовыми 3 генерациями
    await db.add_user(user_id, nick, balance=3)
    await state.clear()
    await message.answer(
        f"Регистрация завершена!\nВаш ник: {nick}\nСтартовый баланс генераций: 3\n"
        "Отправьте файл .mcstructure, чтобы превратить его в .mcpack."
    )

@router.message(Command("profile"))
async def cmd_profile(message: Message):
    user_id = message.from_user.id
    user_data = await db.get_user(user_id)
    if not user_data:
        await message.answer("Вы не зарегистрированы. Используйте /start.")
        return
    nick, balance = user_data
    await message.answer(
        f"Профиль:\nНикнейм: {nick}\nОставшиеся генерации: {balance}"
    )

# ----------------------------------------------------------------------
# Админская команда /add
# ----------------------------------------------------------------------
@router.message(Command("add"))
async def cmd_add(message: Message, command: CommandObject):
    if message.from_user.id != ADMIN_ID:
        await message.answer("Команда доступна только администратору.")
        return

    args = command.args
    if not args:
        await message.answer("Использование: /add <никнейм> <количество>")
        return

    parts = args.split(maxsplit=1)
    if len(parts) != 2:
        await message.answer("Укажите никнейм и количество через пробел.")
        return

    nickname, amount_str = parts
    try:
        amount = int(amount_str)
        if amount <= 0:
            raise ValueError
    except ValueError:
        await message.answer("Количество должно быть положительным целым числом.")
        return

    result = await db.add_balance_by_nickname(nickname, amount)
    if result is None:
        await message.answer(f"Игрок с ником '{nickname}' не найден в базе.")
        return

    _, new_balance = result
    await message.answer(
        f"Баланс игрока {nickname} успешно пополнен на {amount}. "
        f"Текущий баланс: {new_balance}."
    )

# ----------------------------------------------------------------------
# Обработка файлов .mcstructure
# ----------------------------------------------------------------------
@router.message(F.document.file_name.endswith('.mcstructure'))
async def handle_mcstructure(message: Message):
    user_id = message.from_user.id
    # Проверка регистрации
    user_data = await db.get_user(user_id)
    if not user_data:
        await message.answer("Сначала зарегистрируйтесь через /start.")
        return

    nick, balance = user_data
    if balance <= 0:
        await message.answer(
            "У вас закончились генерации. Обратитесь к администратору для пополнения."
        )
        return

    # Уведомляем о начале обработки
    wait_msg = await message.answer("⏳ Обработка структуры, пожалуйста, подождите...")

    try:
        # Скачиваем файл
        file = await bot.get_file(message.document.file_id)
        file_bytes = await bot.download_file(file.file_path)
        raw_data = file_bytes.read()

        # Парсим структуру
        blocks = parser.parse_mcstructure(raw_data)
        if not blocks:
            raise ValueError("Структура не содержит блоков (возможно, пустая).")

        # Генерируем компоненты пака
        geometry = parser.generate_geometry(blocks)
        animation = parser.generate_animation(blocks)
        entity = parser.generate_entity_definition()
        manifest = parser.generate_manifest()

        # Упаковываем .mcpack
        mcpack_bytes = parser.pack_mcpack(geometry, animation, entity, manifest)

        # Списываем 1 генерацию
        await db.update_balance(user_id, -1)

        # Отправляем файл
        original_name = message.document.file_name
        output_name = original_name.replace('.mcstructure', '.mcpack')
        # Используем InputFile из буфера
        from aiogram.types import BufferedInputFile
        input_file = BufferedInputFile(mcpack_bytes, filename=output_name)
        await message.answer_document(input_file, caption="Ваш .mcpack готов ✅")
        await wait_msg.delete()

    except Exception as e:
        logger.error(f"Ошибка обработки mcstructure: {e}", exc_info=True)
        await wait_msg.edit_text(
            "❌ Не удалось обработать файл. Возможно, он повреждён или имеет неверный формат."
        )

# ----------------------------------------------------------------------
# Точка входа
# ----------------------------------------------------------------------
async def main():
    await db.init_db()
    logger.info("База данных инициализирована")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
