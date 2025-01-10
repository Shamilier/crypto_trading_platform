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

    # Получаем текущее соединение
    # conn = Tortoise.get_connection("default")

    # Удаляем все таблицы
    # await conn.execute_script("""
    #     DO $$ DECLARE
    #     r RECORD;
    #     BEGIN
    #         FOR r IN (SELECT tablename FROM pg_tables WHERE schemaname = 'public') LOOP
    #             EXECUTE 'DROP TABLE IF EXISTS ' || quote_ident(r.tablename) || ' CASCADE';
    #         END LOOP;
    #     END $$;
    # """)

    # # Пересоздаём схемы
    # await Tortoise.generate_schemas(safe=True)
    await Tortoise.generate_schemas(safe=True)



async def close():
    await Tortoise.close_connections()

