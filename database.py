import aiosqlite
import os

DB_PATH = "users.db"

async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                telegram_id INTEGER PRIMARY KEY,
                minecraft_nickname TEXT UNIQUE,
                balance_generations INTEGER DEFAULT 3
            )
        """)
        await db.commit()

async def get_user(telegram_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT * FROM users WHERE telegram_id = ?", (telegram_id,))
        row = await cursor.fetchone()
        return dict(row) if row else None

async def get_user_by_nick(nickname: str):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT * FROM users WHERE minecraft_nickname = ?", (nickname,))
        row = await cursor.fetchone()
        return dict(row) if row else None

async def create_user(telegram_id: int, nickname: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("INSERT INTO users (telegram_id, minecraft_nickname, balance_generations) VALUES (?, ?, 3)", 
                         (telegram_id, nickname))
        await db.commit()

async def update_user_balance(telegram_id: int, amount: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE users SET balance_generations = balance_generations + ? WHERE telegram_id = ?", 
                         (amount, telegram_id))
        await db.commit()

async def update_user_balance_by_nick(nickname: str, amount: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE users SET balance_generations = balance_generations + ? WHERE minecraft_nickname = ?", 
                         (amount, nickname))
        await db.commit()
