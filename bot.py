import os
import logging
import shutil
from aiogram import Bot, Dispatcher, Router, types, F
from aiogram.filters import Command, CommandStart
from aiogram.types import Message, FSInputFile
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.storage.memory import MemoryStorage

# Импорт модулей
import database as db
import parser as mc_parser

# --- КОНФИГУРАЦИЯ ---
# Берем данные из переменных окружения Railway
ADMIN_ID = int(os.getenv("ADMIN_ID", 123456789))  # Если не задано, использует 123456789
BOT_TOKEN = os.getenv("BOT_TOKEN")                # Сюда подставится токен из настройки Railway

# Проверка, что токен действительно есть перед запуском
if not BOT_TOKEN:
    raise ValueError("Ошибка: Переменная BOT_TOKEN не найдена в окружении! Проверьте настройки Railway.")

# ... (дальше идет настройка логгирования и бота) ...
logging.basicConfig(level=logging.INFO)
storage = MemoryStorage()
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=storage)
router = Router()

# --- FSM СОСТОЯНИЯ ---
class Form(StatesGroup):
    minecraft_nick = State()

# --- ХЕНДЛЕРЫ ---
@router.message(CommandStart())
async def start_cmd(message: Message, state: FSMContext):
    user = await db.get_user(message.from_user.id)
    if user:
        await message.answer(
            f"👋 Привет, {user['minecraft_nickname']}!\n"
            f"Отправь мне файл .mcstructure, чтобы сгенерировать голограмму.\n"
            f"💰 Баланс генераций: {user['balance_generations']}"
        )
    else:
        await message.answer("🎮 Добро пожаловать! Для начала работы введи свой никнейм в Minecraft:")
        await state.set_state(Form.minecraft_nick)

@router.message(Form.minecraft_nick)
async def process_nickname(message: Message, state: FSMContext):
    nick = message.text.strip()
    if not nick:
        await message.answer("❌ Никнейм не может быть пустым. Попробуй еще раз.")
        return
    
    # Проверяем, не занят ли никнейм в БД
    existing = await db.get_user_by_nick(nick)
    if existing:
        await message.answer("❌ Этот никнейм уже зарегистрирован в системе! Используй /setnick, если это твой ник.")
        return

    await db.create_user(message.from_user.id, nick)
    await state.clear()
    await message.answer(f"✅ Отлично, {nick}! Ты зарегистрирован. Тебе начислено 3 генерации. Отправляй .mcstructure!")

@router.message(Command("setnick"))
async def set_nick_cmd(message: Message, state: FSMContext):
    user = await db.get_user(message.from_user.id)
    if not user:
        await message.answer("❌ Сначала зарегистрируйся командой /start.")
        return
    
    await message.answer("✏️ Введи свой новый никнейм в Minecraft:")
    await state.set_state(Form.minecraft_nick)

# Обработка ввода ника при /setnick (чтобы не пересоздавать пользователя, а обновить)
@router.message(Form.minecraft_nick)
async def process_change_nick(message: Message, state: FSMContext):
    # (Примечание: этот хендлер переопределяет первый, если нужна отдельная логика, 
    # но для упрощения мы используем логику проверки, существовал ли уже этот юзер).
    user = await db.get_user(message.from_user.id)
    if not user:
        # Если вдруг пользователь попал сюда без /start, возвращаем его
        await message.answer("❌ Пожалуйста, начни с команды /start.")
        await state.clear()
        return

    new_nick = message.text.strip()
    if not new_nick:
        await message.answer("❌ Никнейм не может быть пустым.")
        return

    # Проверка, не занят ли новый ник кем-то другим
    existing = await db.get_user_by_nick(new_nick)
    if existing and existing['telegram_id'] != message.from_user.id:
        await message.answer("❌ Этот никнейм уже используется другим пользователем.")
        return

    await db.update_user_nick(message.from_user.id, new_nick)
    await state.clear()
    await message.answer(f"✅ Никнейм успешно изменен на: {new_nick}")

@router.message(F.document)
async def handle_file(message: Message):
    user = await db.get_user(message.from_user.id)
    if not user:
        await message.answer("❌ Сначала зарегистрируйся командой /start и укажи свой Minecraft никнейм.")
        return

    if user['balance_generations'] <= 0:
        await message.answer("❌ Недостаточно генераций на балансе. Обратитесь к администратору.")
        return

    if not message.document.file_name.endswith(".mcstructure"):
        await message.answer("⚠️ Пожалуйста, отправь файл с расширением .mcstructure.")
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
        if os.path.exists(file_path): os.remove(file_path)
        return

    # Генерируем .mcaddon
    mcaddon_path = mc_parser.generate_mcaddon(structure_data)
    
    if not mcaddon_path:
        await message.answer("❌ Ошибка при генерации .mcaddon.")
        if os.path.exists(file_path): os.remove(file_path)
        return

    # Списываем баланс
    await db.update_user_balance(message.from_user.id, -1)

    # Отправляем файл пользователю
    input_file = FSInputFile(mcaddon_path, filename="hologram.mcaddon")
    await message.answer_document(
        document=input_file,
        caption=(
            f"✅ Генерация успешна!\n"
            f"📐 Размер постройки: {structure_data['size']['x']}x{structure_data['size']['y']}x{structure_data['size']['z']}\n"
            f"💰 Остаток баланса: {user['balance_generations'] - 1}\n"
            f"\n🎮 Установи пак в Minecraft и введи команду: /function summon"
        )
    )

    # Удаляем временные файлы, чтобы не забивать память Рэйлвея
    if os.path.exists(file_path): os.remove(file_path)
    if os.path.exists(mcaddon_path): os.remove(mcaddon_path)


# --- АДМИН ПАНЕЛЬ (КОМАНДА ДЛЯ ТЕБЯ) ---
@router.message(Command("add"))
async def add_generations(message: Message):
    if message.from_user.id != ADMIN_ID:
        await message.answer("❌ У тебя нет прав администратора!")
        return

    args = message.text.split()
    if len(args) != 3:
        await message.answer("❌ Неверный формат. Используй: /add [ник_майнкрафт] [количество]")
        return

    nick, amount_str = args[1], args[2]
    try:
        amount = int(amount_str)
        if amount <= 0:
            await message.answer("❌ Количество должно быть больше 0.")
            return
    except ValueError:
        await message.answer("❌ Количество должно быть числом.")
        return

    user = await db.get_user_by_nick(nick)

    if not user:
        await message.answer(f"❌ Пользователь с ником '{nick}' не найден в базе.")
        return

    await db.update_user_balance_by_nick(nick, amount)
    await message.answer(f"✅ Успешно добавлено {amount} генераций пользователю {nick}.\n🆔 ID: {user['telegram_id']}")

# --- ЗАПУСК БОТА ---
async def main():
    dp.include_router(router)
    await db.init_db()
    await dp.start_polling(bot)

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
