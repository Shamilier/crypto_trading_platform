import os
from tortoise import Tortoise
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = f"postgres://{os.getenv('POSTGRES_USER')}:{os.getenv('POSTGRES_PASSWORD')}@db:5432/trading_db"

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

async def init():
    try:
        await Tortoise.init(config=TORTOISE_ORM)
        await Tortoise.generate_schemas(safe=True)
        print("База данных успешно подключена и схемы созданы.")
    except Exception as e:
        print(f"Ошибка подключения к базе данных: {e}")

async def close():
    await Tortoise.close_connections()
