import aiosqlite
from typing import Optional, Tuple

DB_PATH = "bot.db"

async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                telegram_id INTEGER PRIMARY KEY,
                minecraft_nickname TEXT,
                balance_generations INTEGER DEFAULT 0
            )
        """)
        await db.commit()

async def user_exists(telegram_id: int) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("SELECT 1 FROM users WHERE telegram_id = ?", (telegram_id,))
        return await cursor.fetchone() is not None

async def add_user(telegram_id: int, nickname: str, balance: int = 3):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO users (telegram_id, minecraft_nickname, balance_generations) VALUES (?, ?, ?)",
            (telegram_id, nickname, balance)
        )
        await db.commit()

async def get_user(telegram_id: int) -> Optional[Tuple[str, int]]:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT minecraft_nickname, balance_generations FROM users WHERE telegram_id = ?",
            (telegram_id,)
        )
        row = await cursor.fetchone()
        return row if row else None

async def get_balance(telegram_id: int) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("SELECT balance_generations FROM users WHERE telegram_id = ?", (telegram_id,))
        row = await cursor.fetchone()
        return row[0] if row else 0

async def update_balance(telegram_id: int, delta: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE users SET balance_generations = balance_generations + ? WHERE telegram_id = ?",
            (delta, telegram_id)
        )
        await db.commit()

async def add_balance_by_nickname(nickname: str, amount: int) -> Optional[Tuple[int, int]]:
    """Пополняет баланс пользователя по его Minecraft нику. Возвращает (telegram_id, новый баланс) или None."""
    async with aiosqlite.connect(DB_PATH) as db:
        # Находим первого попавшегося по нику (можно ужесточить при необходимости)
        cursor = await db.execute(
            "SELECT telegram_id, balance_generations FROM users WHERE minecraft_nickname = ? LIMIT 1",
            (nickname,)
        )
        row = await cursor.fetchone()
        if not row:
            return None
        tid, cur_bal = row
        new_bal = cur_bal + amount
        await db.execute(
            "UPDATE users SET balance_generations = ? WHERE telegram_id = ?",
            (new_bal, tid)
        )
        await db.commit()
        return tid, new_bal
