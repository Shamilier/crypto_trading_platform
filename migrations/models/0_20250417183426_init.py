from tortoise import BaseDBAsyncClient


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        CREATE TABLE IF NOT EXISTS "bots_info" (
    "id" SERIAL NOT NULL PRIMARY KEY,
    "name" VARCHAR(255) NOT NULL,
    "type" VARCHAR(50) NOT NULL,
    "pnl" DOUBLE PRECISION NOT NULL,
    "crypto_pairs" TEXT NOT NULL,
    "description" TEXT NOT NULL,
    "created_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS "daily_breakdowns" (
    "id" SERIAL NOT NULL PRIMARY KEY,
    "date" DATE NOT NULL,
    "profit_abs" DECIMAL(20,8) NOT NULL,
    "wins" INT NOT NULL,
    "losses" INT NOT NULL,
    "trades_count" INT NOT NULL,
    "profit_factor" DECIMAL(14,6) NOT NULL,
    "bot_info_id" INT NOT NULL REFERENCES "bots_info" ("id") ON DELETE CASCADE,
    CONSTRAINT "uid_daily_break_bot_inf_2366a4" UNIQUE ("bot_info_id", "date")
);
CREATE INDEX IF NOT EXISTS "idx_daily_break_bot_inf_2366a4" ON "daily_breakdowns" ("bot_info_id", "date");
CREATE TABLE IF NOT EXISTS "otp_codes" (
    "id" SERIAL NOT NULL PRIMARY KEY,
    "email" VARCHAR(255) NOT NULL UNIQUE,
    "otp" VARCHAR(6) NOT NULL,
    "expires_at" TIMESTAMPTZ NOT NULL,
    "created_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS "trades" (
    "id" SERIAL NOT NULL PRIMARY KEY,
    "pair" VARCHAR(32) NOT NULL,
    "stake_amount" DECIMAL(20,8) NOT NULL,
    "open_date" TIMESTAMPTZ NOT NULL,
    "close_date" TIMESTAMPTZ NOT NULL,
    "profit_abs" DECIMAL(20,8) NOT NULL,
    "profit_ratio" DECIMAL(12,6) NOT NULL,
    "trade_duration" INT NOT NULL,
    "exit_reason" VARCHAR(64),
    "is_short" BOOL NOT NULL,
    "bot_info_id" INT NOT NULL REFERENCES "bots_info" ("id") ON DELETE CASCADE,
    CONSTRAINT "uid_trades_bot_inf_010100" UNIQUE ("bot_info_id", "open_date", "pair")
);
CREATE INDEX IF NOT EXISTS "idx_trades_bot_inf_6599ee" ON "trades" ("bot_info_id", "open_date");
CREATE TABLE IF NOT EXISTS "users" (
    "id" SERIAL NOT NULL PRIMARY KEY,
    "email" VARCHAR(255) NOT NULL UNIQUE,
    "refresh_token" VARCHAR(255) NOT NULL UNIQUE,
    "refresh_token_expires_at" TIMESTAMPTZ NOT NULL,
    "is_trial" BOOL NOT NULL,
    "subscription_expires_at" TIMESTAMPTZ NOT NULL,
    "created_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS "api_keys" (
    "id" SERIAL NOT NULL PRIMARY KEY,
    "name" VARCHAR(50) NOT NULL,
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
    "password" VARCHAR(255) NOT NULL,
    "status" VARCHAR(50) NOT NULL DEFAULT 'inactive',
    "available_capital" DOUBLE PRECISION NOT NULL,
    "is_dry_run" BOOL NOT NULL,
    "port" INT NOT NULL,
    "container_id" VARCHAR(255) NOT NULL,
    "created_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "api_key_id" INT NOT NULL REFERENCES "api_keys" ("id") ON DELETE CASCADE,
    "user_id" INT NOT NULL REFERENCES "users" ("id") ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS "payments" (
    "id" SERIAL NOT NULL PRIMARY KEY,
    "yookassa_id" VARCHAR(50) NOT NULL,
    "paid" BOOL NOT NULL,
    "created_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
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
