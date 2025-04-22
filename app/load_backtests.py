# app/load_backtests.py
"""
Импорт *.json из user_data/example/backtest_results → trades / daily_breakdowns
Запуск внутри контейнера:
    docker-compose exec app python3 -m app.load_backtests
"""
import os, json, asyncio
from decimal import Decimal
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv

from tortoise import Tortoise
from tortoise.transactions import in_transaction
from tortoise.exceptions import DoesNotExist

load_dotenv()

DB_URL       = os.getenv("DATABASE_URL")
BACKTEST_DIR = Path('./user_data/example/backtest_results')


from app.models import BotInfo, Trade, DailyBreakdown   # модели

# ────────────────────────────────────────────────────────────────
async def _load_file(fp: Path):
    bot_name = fp.stem.replace("_backtest", "")

    try:
        bot = await BotInfo.get(name=bot_name)
    except DoesNotExist:
        print(f"⚠  BotInfo «{bot_name}» не найден — {fp.name} пропущен")
        return

    raw         = json.loads(fp.read_text())
    strat_key   = next(iter(raw["strategy"]))
    strat_data  = raw["strategy"][strat_key]

    trades = [
        Trade(
            bot_info      = bot,
            pair          = t["pair"],
            stake_amount  = Decimal(str(t["stake_amount"])),
            open_date     = datetime.fromisoformat(t["open_date"]),
            close_date    = datetime.fromisoformat(t["close_date"]),
            profit_abs    = Decimal(str(t["profit_abs"])),
            profit_ratio  = Decimal(str(t["profit_ratio"])),
            trade_duration= int(t["trade_duration"]),
            exit_reason   = t.get("exit_reason"),
            is_short      = bool(t["is_short"]),
        )
        for t in strat_data.get("trades", [])
    ]

    daily = [
        DailyBreakdown(
            bot_info      = bot,
            date          = datetime.strptime(d["date"], "%d/%m/%Y").date(),
            profit_abs    = Decimal(str(d["profit_abs"])),
            wins          = d["wins"],
            losses        = d["losses"],
            trades_count  = d["trades"],
            profit_factor = Decimal(str(d["profit_factor"])),
        )
        for d in strat_data.get("periodic_breakdown", {}).get("day", [])
    ]

    async with in_transaction():
        if trades:
            await Trade.bulk_create(trades, ignore_conflicts=True)
        if daily:
            await DailyBreakdown.bulk_create(daily, ignore_conflicts=True)

    print(f"✔ {fp.name}: {len(trades)} trades, {len(daily)} days")


# ────────────────────────────────────────────────────────────────
async def import_backtests():
    print("▶️  Импорт backtests…")
    files = sorted(BACKTEST_DIR.glob("*_backtest.json"))
    if not files:
        print("❌  Файлы не найдены в", BACKTEST_DIR)
        return

    for fp in files:
        await _load_file(fp)

    print("✅  Импорт завершён")


# ────────────────────────────────────────────────────────────────
async def main():
    # 1. Инициализируем Tortoise
    await Tortoise.init(
        db_url=DB_URL,
        modules={"models": ["app.models"]},
    )

    # 2. Импортируем backtests
    await import_backtests()

    # 3. Закрываем соединения
    await Tortoise.close_connections()
    print("🏁  Done.")


if __name__ == "__main__":
    asyncio.run(main())