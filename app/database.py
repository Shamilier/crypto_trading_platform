from tortoise import Tortoise
import asyncpg

DATABASE_URL = "postgres://postgres:password@db:5432/trading_db"

TORTOISE_ORM = {
    "connections": {
        "default": DATABASE_URL,
    },
    "apps": {
        "models": {
            "models": ["app.models", "aerich.models"],
            "default_connection": "default",
        },
    },
}

async def ensure_database_exists():
    """
    Проверяет наличие базы данных trading_db, если её нет — создаёт.
    """
    dsn = DATABASE_URL.replace("/trading_db", "/postgres")
    conn = await asyncpg.connect(dsn)
    try:
        # Проверяем наличие базы данных
        result = await conn.fetchval("SELECT 1 FROM pg_database WHERE datname = 'trading_db'")
        if not result:
            # Создаём базу данных, если она отсутствует
            await conn.execute("CREATE DATABASE trading_db")
            print("База данных trading_db была создана.")
        else:
            print("База данных trading_db уже существует.")
    finally:
        await conn.close()

async def init():
    """
    Инициализация базы данных и ORM.
    """
    await ensure_database_exists()  # Проверяем и создаём базу данных, если нужно
    await Tortoise.init(config=TORTOISE_ORM)  # Подключаемся через Tortoise ORM
    await Tortoise.generate_schemas(safe=True)  # Генерируем схемы (таблицы)

async def close():
    """
    Закрывает соединения с базой данных.
    """
    await Tortoise.close_connections()
