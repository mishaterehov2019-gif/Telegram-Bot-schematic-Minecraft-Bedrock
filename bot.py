import os
import logging
import shutil
from aiogram import Bot, Dispatcher, Router, types, F
from aiogram.filters import Command, CommandStart
from aiogram.types import Message, FSInputFile
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.storage.memory import MemoryStorage
import database as db
import parser as mc_parser

# Настройки
ADMIN_ID = 123456789  # Замени на свой ID
BOT_TOKEN = "ВАШ_ТОКЕН_БОТА" # Токен из Variable на Railway

logging.basicConfig(level=logging.INFO)
storage = MemoryStorage()
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=storage)
router = Router()

# Состояния FSM для регистрации ника
class Form(StatesGroup):
    minecraft_nick = State()

@router.message(CommandStart())
async def start_cmd(message: Message, state: FSMContext):
    user = await db.get_user(message.from_user.id)
    if user:
        await message.answer(f"Привет, {user['minecraft_nickname']}! Отправь мне файл .mcstructure чтобы сгенерировать голограмму. Баланс: {user['balance_generations']}")
    else:
        await message.answer("Добро пожаловать! Для начала работы введи свой никнейм в Minecraft:")
        await state.set_state(Form.minecraft_nick)

@router.message(Form.minecraft_nick)
async def process_nickname(message: Message, state: FSMContext):
    nick = message.text.strip()
    if not nick:
        await message.answer("Никнейм не может быть пустым. Попробуй еще раз.")
        return
    
    # Проверяем, занят ли никнейм в БД
    existing = await db.get_user_by_nick(nick)
    if existing:
        await message.answer("Этот никнейм уже зарегистрирован в системе! Используй /setnick если это ты.")
        return

    await db.create_user(message.from_user.id, nick)
    await state.clear()
    await message.answer(f"Отлично, {nick}! Ты зарегистрирован. Тебе начислено 3 генерации. Отправляй .mcstructure!")

@router.message(Command("setnick"))
async def set_nick_cmd(message: Message, state: FSMContext):
    await message.answer("Введи свой новый никнейм в Minecraft:")
    await state.set_state(Form.minecraft_nick)

@router.message(F.document)
async def handle_file(message: Message):
    user = await db.get_user(message.from_user.id)
    if not user:
        await message.answer("Сначала зарегистрируйся командой /start и укажи свой Minecraft никнейм.")
        return

    if user['balance_generations'] <= 0:
        await message.answer("❌ Недостаточно генераций на балансе. Обратитесь к администратору.")
        return

    if not message.document.file_name.endswith(".mcstructure"):
        await message.answer("Пожалуйста, отправь файл с расширением .mcstructure.")
        return

    # Скачиваем файл
    file = await bot.get_file(message.document.file_id)
    file_path = f"/tmp/{message.document.file_name}"
    await bot.download_file(file.file_path, file_path)

    # Парсим структуру
    await message.answer("⏳ Начинаю парсинг и генерацию пака...")
    structure_data = mc_parser.parse_mcstructure(file_path)
    
    if not structure_data:
        await message.answer("❌ Ошибка: Файл .mcstructure поврежден или имеет неверный формат.")
        return

    # Генерируем .mcaddon
    mcaddon_path = mc_parser.generate_mcaddon(structure_data)
    
    if not mcaddon_path:
        await message.answer("❌ Ошибка при генерации .mcaddon.")
        return

    # Списываем баланс
    await db.update_user_balance(message.from_user.id, -1)

    # Отправляем файл пользователю
    input_file = FSInputFile(mcaddon_path, filename="hologram.mcaddon")
    await message.answer_document(
        document=input_file,
        caption=f"✅ Генерация успешна! Размер постройки: {structure_data['size']['x']}x{structure_data['size']['y']}x{structure_data['size']['z']}. Баланс: {user['balance_generations'] - 1}"
    )

    # Чистим мусор
    os.remove(file_path)
    os.remove(mcaddon_path)

# --- АДМИН ПАНЕЛЬ ---
@router.message(Command("add"))
async def add_generations(message: Message):
    if message.from_user.id != ADMIN_ID:
        await message.answer("❌ Ты не администратор!")
        return

    args = message.text.split()
    if len(args) != 3:
        await message.answer("❌ Неверный формат. Используй: /add [ник_майнкрафт] [количество]")
        return

    nick, amount = args[1], int(args[2])
    user = await db.get_user_by_nick(nick)

    if not user:
        await message.answer(f"❌ Пользователь с ником '{nick}' не найден в базе.")
        return

    await db.update_user_balance_by_nick(nick, amount)
    await message.answer(f"✅ Успешно добавлено {amount} генераций пользователю {nick}.")

async def main():
    dp.include_router(router)
    await db.init_db()
    await dp.start_polling(bot)

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
