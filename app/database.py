from tortoise import Tortoise

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
    await Tortoise.init(config=TORTOISE_ORM)
    await Tortoise.generate_schemas(safe=True)  # Пересоздание схемы без миграций


async def close():
    await Tortoise.close_connections()

