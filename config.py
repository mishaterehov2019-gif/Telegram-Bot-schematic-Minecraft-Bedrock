import os

BOT_TOKEN = os.getenv("BOT_TOKEN", "ВАШ_ТОКЕН_БОТА")
ADMIN_ID = int(os.getenv("ADMIN_ID", "123456789"))  # Ваш Telegram ID

# Пути
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TEMPLATE_DIR = os.path.join(BASE_DIR, "templates")
DATABASE_PATH = os.path.join(BASE_DIR, "data", "bot.db")

# Создаём папки
os.makedirs(os.path.join(BASE_DIR, "data"), exist_ok=True)
os.makedirs(TEMPLATE_DIR, exist_ok=True)
