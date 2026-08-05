import aiosqlite
from config import DATABASE_PATH
from typing import Optional, Tuple

class Database:
    def __init__(self):
        self.db_path = DATABASE_PATH

    async def init_db(self):
        """Создаёт таблицы при первом запуске"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    telegram_id INTEGER PRIMARY KEY,
                    minecraft_nickname TEXT UNIQUE NOT NULL,
                    balance_generations INTEGER DEFAULT 3,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            await db.commit()

    async def register_user(self, telegram_id: int, minecraft_nickname: str) -> bool:
        """Регистрирует нового пользователя"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute(
                    "INSERT INTO users (telegram_id, minecraft_nickname, balance_generations) VALUES (?, ?, 3)",
                    (telegram_id, minecraft_nickname)
                )
                await db.commit()
                return True
        except aiosqlite.IntegrityError:
            return False  # Ник уже занят

    async def get_user(self, telegram_id: int) -> Optional[Tuple]:
        """Получает данные пользователя"""
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute(
                "SELECT telegram_id, minecraft_nickname, balance_generations FROM users WHERE telegram_id = ?",
                (telegram_id,)
            ) as cursor:
                return await cursor.fetchone()

    async def get_user_by_nickname(self, minecraft_nickname: str) -> Optional[Tuple]:
        """Ищет пользователя по нику (для админа)"""
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute(
                "SELECT telegram_id, minecraft_nickname, balance_generations FROM users WHERE minecraft_nickname = ?",
                (minecraft_nickname,)
            ) as cursor:
                return await cursor.fetchone()

    async def update_nickname(self, telegram_id: int, new_nickname: str) -> bool:
        """Обновляет никнейм пользователя"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute(
                    "UPDATE users SET minecraft_nickname = ? WHERE telegram_id = ?",
                    (new_nickname, telegram_id)
                )
                await db.commit()
                return True
        except aiosqlite.IntegrityError:
            return False  # Ник занят

    async def add_generations(self, minecraft_nickname: str, amount: int) -> Tuple[bool, str]:
        """Добавляет генерации пользователю (для админа)"""
        async with aiosqlite.connect(self.db_path) as db:
            # Проверяем, существует ли пользователь
            async with db.execute(
                "SELECT telegram_id, balance_generations FROM users WHERE minecraft_nickname = ?",
                (minecraft_nickname,)
            ) as cursor:
                user = await cursor.fetchone()
                if not user:
                    return False, f"Пользователь с ником {minecraft_nickname} не найден"

            # Обновляем баланс
            await db.execute(
                "UPDATE users SET balance_generations = balance_generations + ? WHERE minecraft_nickname = ?",
                (amount, minecraft_nickname)
            )
            await db.commit()

            # Получаем новый баланс
            async with db.execute(
                "SELECT balance_generations FROM users WHERE minecraft_nickname = ?",
                (minecraft_nickname,)
            ) as cursor:
                new_balance = await cursor.fetchone()
                return True, f"✅ Добавлено {amount} генераций пользователю {minecraft_nickname}. Новый баланс: {new_balance[0]}"

    async def use_generation(self, telegram_id: int) -> bool:
        """Списывает одну генерацию"""
        async with aiosqlite.connect(self.db_path) as db:
            # Проверяем баланс
            async with db.execute(
                "SELECT balance_generations FROM users WHERE telegram_id = ?",
                (telegram_id,)
            ) as cursor:
                user = await cursor.fetchone()
                if not user or user[0] <= 0:
                    return False

            # Списываем генерацию
            await db.execute(
                "UPDATE users SET balance_generations = balance_generations - 1 WHERE telegram_id = ?",
                (telegram_id,)
            )
            await db.commit()
            return True

    async def get_balance(self, telegram_id: int) -> int:
        """Получает текущий баланс"""
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute(
                "SELECT balance_generations FROM users WHERE telegram_id = ?",
                (telegram_id,)
            ) as cursor:
                result = await cursor.fetchone()
                return result[0] if result else 0

db = Database()