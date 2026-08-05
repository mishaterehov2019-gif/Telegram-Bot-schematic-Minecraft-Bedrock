# db.py
import aiosqlite

DB_PATH = "bot.db"

async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                telegram_id INTEGER PRIMARY KEY,
                minecraft_nickname TEXT NOT NULL,
                balance_generations INTEGER DEFAULT 3
            )
        """)
        await db.commit()

async def get_user(telegram_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT * FROM users WHERE telegram_id = ?", (telegram_id,))
        return await cursor.fetchone()

async def create_user(telegram_id: int, nickname: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("INSERT INTO users (telegram_id, minecraft_nickname, balance_generations) VALUES (?, ?, 3)",
                         (telegram_id, nickname))
        await db.commit()

async def update_balance(telegram_id: int, delta: int) -> int:
    """Изменяет баланс на delta и возвращает новое значение."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE users SET balance_generations = balance_generations + ? WHERE telegram_id = ?",
                         (delta, telegram_id))
        await db.commit()
        cursor = await db.execute("SELECT balance_generations FROM users WHERE telegram_id = ?", (telegram_id,))
        row = await cursor.fetchone()
        return row[0] if row else 0

async def get_user_by_nickname(nickname: str):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT * FROM users WHERE minecraft_nickname = ?", (nickname,))
        return await cursor.fetchone()
