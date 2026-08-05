import os
import tempfile
import asyncio
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import Message, CallbackQuery, FSInputFile
from aiogram.utils.formatting import Text, Bold, Italic, Code

from config import BOT_TOKEN, ADMIN_ID, BASE_DIR
from database import db
from parser import get_generator

# Инициализация
bot = Bot(token=BOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)
generator = get_generator()

# Состояния FSM
class Registration(StatesGroup):
    waiting_for_nickname = State()

class AdminAdd(StatesGroup):
    waiting_for_nickname = State()
    waiting_for_amount = State()

# --- Хендлеры ---
@dp.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext):
    """Обработчик команды /start"""
    user = await db.get_user(message.from_user.id)

    if user:
        # Пользователь уже зарегистрирован
        telegram_id, nickname, balance = user
        await message.answer(
            f"👋 Привет, {nickname}!\n\n"
            f"📊 Твой баланс: {balance} генераций\n\n"
            f"📤 Отправь мне .mcstructure файл для создания голограммы!\n"
            f"🔄 Команда /setnick [ник] - изменить никнейм"
        )
    else:
        # Запрашиваем никнейм
        await state.set_state(Registration.waiting_for_nickname)
        await message.answer(
            "🎮 Добро пожаловать!\n\n"
            "Для начала работы введи свой никнейм в Minecraft Bedrock:\n"
            "Пример: `Steve` или `Alex_123`",
            parse_mode="Markdown"
        )

@dp.message(Registration.waiting_for_nickname)
async def process_nickname(message: Message, state: FSMContext):
    """Обработка ввода никнейма"""
    nickname = message.text.strip()

    if len(nickname) < 2 or len(nickname) > 16:
        await message.answer("❌ Ник должен быть от 2 до 16 символов. Попробуй ещё раз:")
        return

    # Регистрируем пользователя
    success = await db.register_user(message.from_user.id, nickname)

    if success:
        await state.clear()
        await message.answer(
            f"✅ Отлично, {nickname}! Ты зарегистрирован!\n\n"
            f"🎁 На балансе: 3 генерации\n\n"
            f"📤 Отправь мне .mcstructure файл, чтобы создать голограмму!"
        )
    else:
        await message.answer(
            f"❌ Ник `{nickname}` уже занят! Пожалуйста, выбери другой:",
            parse_mode="Markdown"
        )

@dp.message(Command("setnick"))
async def cmd_setnick(message: Message):
    """Изменение никнейма"""
    args = message.text.split(maxsplit=1)

    if len(args) < 2:
        await message.answer("❌ Использование: `/setnick [новый_ник]`", parse_mode="Markdown")
        return

    new_nick = args[1].strip()

    if len(new_nick) < 2 or len(new_nick) > 16:
        await message.answer("❌ Ник должен быть от 2 до 16 символов.")
        return

    success = await db.update_nickname(message.from_user.id, new_nick)

    if success:
        await message.answer(f"✅ Никнейм изменён на `{new_nick}`!", parse_mode="Markdown")
    else:
        await message.answer(f"❌ Ник `{new_nick}` уже занят! Попробуй другой.")

@dp.message(Command("balance"))
async def cmd_balance(message: Message):
    """Проверка баланса"""
    balance = await db.get_balance(message.from_user.id)
    user = await db.get_user(message.from_user.id)

    if user:
        _, nickname, _ = user
        await message.answer(
            f"📊 Твой баланс, {nickname}:\n\n"
            f"💰 {balance} генераций\n\n"
            f"Каждая конвертация тратит 1 генерацию."
        )
    else:
        await message.answer("❌ Сначала зарегистрируйся через /start")

@dp.message(Command("add"))
async def cmd_add(message: Message):
    """Админская команда добавления генераций"""
    if message.from_user.id != ADMIN_ID:
        await message.answer("⛔ Доступ запрещён. Только для администратора.")
        return

    args = message.text.split(maxsplit=2)

    if len(args) < 3:
        await message.answer("❌ Использование: `/add [ник_майнкрафт] [количество]`", parse_mode="Markdown")
        return

    nickname, amount_str = args[1], args[2]

    try:
        amount = int(amount_str)
        if amount <= 0:
            await message.answer("❌ Количество должно быть положительным числом.")
            return
    except ValueError:
        await message.answer("❌ Количество должно быть числом.")
        return

    success, result = await db.add_generations(nickname, amount)

    if success:
        await message.answer(f"✅ {result}")

        # Уведомляем пользователя
        user = await db.get_user_by_nickname(nickname)
        if user:
            telegram_id, _, _ = user
            try:
                await bot.send_message(
                    telegram_id,
                    f"🎉 Администратор добавил тебе {amount} генераций!\n"
                    f"Новый баланс: {await db.get_balance(telegram_id)}"
                )
            except:
                pass  # Не отправлено - ничего страшного
    else:
        await message.answer(f"❌ {result}")

@dp.message(F.document)
async def handle_file(message: Message):
    """Обработчик файлов .mcstructure"""
    user = await db.get_user(message.from_user.id)

    if not user:
        await message.answer("❌ Сначала зарегистрируйся через /start")
        return

    telegram_id, nickname, balance = user

    # Проверяем баланс
    if balance <= 0:
        await message.answer(
            "❌ Недостаточно генераций на балансе!\n"
            f"Баланс: {balance}\n"
            "Обратитесь к администратору для пополнения."
        )
        return

    # Проверяем расширение файла
    if not message.document.file_name.endswith('.mcstructure'):
        await message.answer("❌ Пожалуйста, отправь файл с расширением `.mcstructure`")
        return

    # Проверяем размер файла (макс 10MB)
    if message.document.file_size > 10 * 1024 * 1024:
        await message.answer("❌ Файл слишком большой (>10MB). Используй структуру поменьше.")
        return

    # Отправляем статус
    status_msg = await message.answer("⏳ Загрузка и обработка файла...")

    try:
        # Скачиваем файл
        file = await bot.get_file(message.document.file_id)
        file_path = await bot.download_file(file.file_path)

        # Сохраняем во временный файл
        with tempfile.NamedTemporaryFile(suffix='.mcstructure', delete=False) as tmp_file:
            tmp_file.write(file_path.read())
            tmp_file_path = tmp_file.name

        # Парсим и генерируем голограмму
        await status_msg.edit_text("🔄 Парсинг структуры...")

        structure_data = generator.parse_mcstructure(tmp_file_path)

        if not structure_data:
            await status_msg.edit_text("❌ Не удалось прочитать файл. Возможно, он повреждён.")
            os.unlink(tmp_file_path)
            return

        # Генерируем пак
        await status_msg.edit_text("🏗️ Создание голограммы...")

        output_path = os.path.join(os.path.dirname(tmp_file_path), "holo.mcpack")
        success, msg, block_count = generator.generate_holo_pack(structure_data, output_path)

        if not success:
            await status_msg.edit_text(f"❌ {msg}")
            os.unlink(tmp_file_path)
            return

        # Списываем генерацию
        await db.use_generation(telegram_id)

        # Отправляем результат
        await status_msg.edit_text(
            f"✅ Голограмма готова!\n\n"
            f"🏷️ {structure_data['name']}\n"
            f"🧱 Блоков: {block_count}\n"
            f"📏 Размер: {structure_data['size']['x']}x{structure_data['size']['y']}x{structure_data['size']['z']}\n\n"
            f"📦 Установи файл в Minecraft Bedrock\n"
            f"⚙️ В игре введи: `/function spawn_holo`\n\n"
            f"💰 Осталось генераций: {await db.get_balance(telegram_id)}"
        )

        # Отправляем файл
        await bot.send_document(
            message.chat.id,
            FSInputFile(output_path),
            caption=f"📦 Голограмма для {nickname}"
        )

        # Удаляем временные файлы
        os.unlink(tmp_file_path)
        os.unlink(output_path)

    except Exception as e:
        await status_msg.edit_text(f"❌ Произошла ошибка: {str(e)}")
        import traceback
        traceback.print_exc()

@dp.message(Command("help"))
async def cmd_help(message: Message):
    """Команда помощи"""
    await message.answer(
        "📖 **Доступные команды:**\n\n"
        "/start - Начать работу (регистрация)\n"
        "/setnick [ник] - Изменить никнейм\n"
        "/balance - Проверить баланс\n"
        "/help - Эта справка\n\n"
        "📤 **Как использовать:**\n"
        "1. Зарегистрируйся через /start\n"
        "2. Отправь мне .mcstructure файл\n"
        "3. Получи .mcpack с голограммой\n"
        "4. Установи в Minecraft и используй /function spawn_holo\n\n"
        "🔄 **Управление слоями:**\n"
        "В игре используй предметы для переключения слоёв.",
        parse_mode="Markdown"
    )

# --- Запуск ---
async def main():
    """Главная функция запуска"""
    # Инициализируем БД
    await db.init_db()

    # Запускаем бота
    print("🤖 Бот запущен!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())