import os
import asyncio
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import FSInputFile

import db
import parser

# КОНФИГУРАЦИЯ БОТА (Замените на свои данные)
TOKEN = "8987954193:AAEbC9h7SPAmAWlhOjEwrD0xle1t0zLb7eA"
ADMIN_ID = 123456789  # Ваш реальный Telegram ID цифрами

bot = Bot(token=TOKEN)
dp = Dispatcher()

class Registration(StatesGroup):
    waiting_for_nickname = State()

@dp.message(Command("start"))
async def cmd_start(message: types.Message, state: FSMContext):
    user = await db.get_user(message.from_user.id)
    if user:
        # Если уже зарегистрирован, выводим данные профиля
        await message.answer(
            f"👤 Ваш профиль:\n"
            f"┣ Ник в Minecraft: `{user['minecraft_nickname']}`\n"
            f"┗ Доступно генераций: *{user['balance_generations']}*\n\n"
            f"Отправьте мне файл `.mcstructure`, чтобы создать голограмму."
        )
    else:
        # Первая регистрация
        await message.answer("Добро пожаловать в HoloPrint бот!\nВведите ваш никнейм в Майнкрафте для регистрации:")
        await state.set_state(Registration.waiting_for_nickname)

@dp.message(Registration.waiting_for_nickname)
async def process_nickname(message: types.Message, state: FSMContext):
    nickname = message.text.strip()
    if len(nickname) < 3 or " " in nickname:
        await message.answer("Некорректный никнейм. Пожалуйста, введите правильный ник без пробелов:")
        return
    
    await db.register_user(message.from_user.id, nickname)
    await state.clear()
    await message.answer(
        f"Регистрация успешна! Ваш ник: `{nickname}`\n"
        f"Вам начислено 3 стартовые генерации.\n"
        f"Теперь вы можете отправить файл `.mcstructure`."
    )

@dp.message(Command("profile"))
async def cmd_profile(message: types.Message):
    user = await db.get_user(message.from_user.id)
    if not user:
        await message.answer("Вы не зарегистрированы. Напишите /start")
        return
    await message.answer(
        f"👤 Профиль игрока:\n"
        f"┣ Ник: `{user['minecraft_nickname']}`\n"
        f"┗ Баланс: *{user['balance_generations']}* генераций"
    )

# Команда администратора для начисления баланса
@dp.message(Command("add"))
async def cmd_add_balance(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        return # Игнорируем, если пишет не админ

    args = message.text.split()
    if len(args) != 3:
        await message.answer("Ошибка! Формат команды: `/add [ник_майнкрафт] [количество]`")
        return
        
    target_nick = args[1]
    try:
        amount = int(args[2])
    except ValueError:
        await message.answer("Количество должно быть целым числом.")
        return

    new_balance = await db.update_balance(target_nick, amount)
    if new_balance is None:
        await message.answer(f"Пользователь с ником `{target_nick}` не найден в базе данных.")
    else:
        await message.answer(f"Баланс игрока `{target_nick}` успешно изменен. Текущий баланс: *{new_balance}*")

# Обработчик входящих файлов структур
@dp.message(F.document)
async def handle_structure_file(message: types.Message):
    user = await db.get_user(message.from_user.id)
    if not user:
        await message.answer("Сначала зарегистрируйтесь, отправив команду /start")
        return
        
    if user['balance_generations'] <= 0:
        await message.answer("Недостаточно генераций на балансе. Обратитесь к администратору для пополнения.")
        return

    document = message.document
    if not document.file_name.endswith('.mcstructure'):
        await message.answer("Пожалуйста, отправьте корректный файл структуры с расширением `.mcstructure`")
        return

    status_msg = await message.answer("⏳ Чтение структуры и генерация голограммы... Пожалуйста, подождите.")
    
    # Скачивание файла
    os.makedirs("downloads", exist_ok=True)
    os.makedirs("output", exist_ok=True)
    
    file_path = f"downloads/{document.file_id}.mcstructure"
    await bot.download(document.file_id, destination=file_path)

    try:
        # Процесс парсинга и сборки ресурс-пака
        mcpack_output = parser.compile_mcpack(file_path, "output", document.file_id)
        
        # Списание генерации
        await db.decrease_balance(message.from_user.id)
        
        # Отправка готового файла пользователю
        input_file = FSInputFile(mcpack_output, filename=f"HoloPrint_{user['minecraft_nickname']}.mcpack")
        await message.answer_document(
            document=input_file, 
            caption="✅ Голограмма успешно создана!\nИмпортируйте этот `.mcpack` в Minecraft. Поставьте стойку для брони и меняйте её позы для переключения слоев."
        )
        
        # Удаление временного mcpack
        if os.path.exists(mcpack_output):
            os.remove(mcpack_output)
            
    except Exception as e:
        await message.answer(f"❌ Произошла ошибка при обработке файла: {e}\nУбедитесь, что это валидный .mcstructure файл Bedrock Edition.")
    finally:
        # Очистка входящего файла
        if os.path.exists(file_path):
            os.remove(file_path)
        await status_msg.delete()

async def main():
    await db.init_db()
    print("База данных запущена, бот начинает опрос серверов...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
