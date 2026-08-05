import aiosqlite

DB_NAME = "holoprint.db"

async def init_db():
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                telegram_id INTEGER PRIMARY KEY,
                minecraft_nickname TEXT UNIQUE,
                balance_generations INTEGER DEFAULT 3
            )
        """)
        await db.commit()

async def get_user(telegram_id: int):
    async with aiosqlite.connect(DB_NAME) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM users WHERE telegram_id = ?", (telegram_id,)) as cursor:
            return await cursor.fetchone()

async def get_user_by_nick(nickname: str):
    async with aiosqlite.connect(DB_NAME) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM users WHERE minecraft_nickname = ?", (nickname,)) as cursor:
            return await cursor.fetchone()

async def register_user(telegram_id: int, nickname: str):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute(
            "INSERT OR IGNORE INTO users (telegram_id, minecraft_nickname, balance_generations) VALUES (?, ?, 3)",
            (telegram_id, nickname)
        )
        await db.commit()

async def update_balance(nickname: str, amount: int):
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("SELECT balance_generations FROM users WHERE minecraft_nickname = ?", (nickname,)) as cursor:
            row = await cursor.fetchone()
            if not row:
                return None
            new_balance = row[0] + amount
            await db.execute(
                "UPDATE users SET balance_generations = ? WHERE minecraft_nickname = ?",
                (new_balance, nickname)
            )
            await db.commit()
            return new_balance

async def decrease_balance(telegram_id: int):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute(
            "UPDATE users SET balance_generations = balance_generations - 1 WHERE telegram_id = ?",
            (telegram_id,)
        )
        await db.commit()
