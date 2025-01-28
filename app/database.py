import os
from tortoise import Tortoise

# DATABASE_URL = "postgres://postgres:password@0.0.0.0:5432/trading_db"
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

async def init():
    try:
        await Tortoise.init(config=TORTOISE_ORM)
        await Tortoise.generate_schemas(safe=True)
        print("База данных успешно подключена и схемы созданы.")
    except Exception as e:
        print(f"Ошибка подключения к базе данных: {e}")

async def close():
    await Tortoise.close_connections()
