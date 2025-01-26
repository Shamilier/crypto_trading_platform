from tortoise import BaseDBAsyncClient


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        CREATE TABLE IF NOT EXISTS "users" (
    "id" SERIAL NOT NULL PRIMARY KEY,
    "username" VARCHAR(50) NOT NULL UNIQUE,
    "hashed_password" VARCHAR(128) NOT NULL,
    "email" VARCHAR(255) NOT NULL UNIQUE
);
CREATE TABLE IF NOT EXISTS "api_keys" (
    "id" SERIAL NOT NULL PRIMARY KEY,
    "exchange" VARCHAR(50) NOT NULL,
    "api_key" TEXT NOT NULL,
    "secret_key" TEXT NOT NULL,
    "created_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "user_id" INT NOT NULL REFERENCES "users" ("id") ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS "bots" (
    "id" SERIAL NOT NULL PRIMARY KEY,
    "name" VARCHAR(255) NOT NULL,
    "strategy" VARCHAR(255) NOT NULL,
    "status" VARCHAR(50) NOT NULL DEFAULT 'inactive',
    "balance_used" DOUBLE PRECISION NOT NULL DEFAULT 0,
    "indicators" JSONB NOT NULL,
    "profit" DOUBLE PRECISION NOT NULL DEFAULT 0,
    "created_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "user_id" INT NOT NULL REFERENCES "users" ("id") ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS "containers" (
    "id" SERIAL NOT NULL PRIMARY KEY,
    "container_id" VARCHAR(255) NOT NULL,
    "port" INT NOT NULL,
    "status" VARCHAR(50) NOT NULL DEFAULT 'running',
    "created_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "user_id" INT NOT NULL REFERENCES "users" ("id") ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS "refreshtoken" (
    "id" SERIAL NOT NULL PRIMARY KEY,
    "token" VARCHAR(255) NOT NULL UNIQUE,
    "expires_at" TIMESTAMPTZ NOT NULL,
    "user_id" INT NOT NULL REFERENCES "users" ("id") ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS "aerich" (
    "id" SERIAL NOT NULL PRIMARY KEY,
    "version" VARCHAR(255) NOT NULL,
    "app" VARCHAR(100) NOT NULL,
    "content" JSONB NOT NULL
);"""


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
        """
