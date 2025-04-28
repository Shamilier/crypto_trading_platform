import json
import glob

# Путь к файлу результата
result_file = "/Users/shamilgaliev18mail.ru/cry/crypto_trading_platform/user_data/example/backtest_results/BB.json"

# Список исходных файлов
source_files = ["/Users/shamilgaliev18mail.ru/cry/crypto_trading_platform/user_data/example/backtest_results/u111-2025-04-28_11-17-45.json",
                 "/Users/shamilgaliev18mail.ru/cry/crypto_trading_platform/user_data/example/backtest_results/u222-2025-04-28_11-20-43.json",
                   "/Users/shamilgaliev18mail.ru/cry/crypto_trading_platform/user_data/example/backtest_results/u333-2025-04-28_11-24-04.json"]

# Загрузка начального result файла
with open(result_file, "r") as rf:
    result_data = json.load(rf)

# Чистим изначальные trades и day
result_data["strategy"]["BB_RTR"]["trades"] = []
result_data["strategy"]["BB_RTR"]["periodic_breakdown"]["day"] = []

# Проходим по каждому исходному файлу
for src_file in source_files:
    with open(src_file, "r") as sf:
        src_data = json.load(sf)

    # Проверяем наличие нужных данных
    trades = src_data.get("strategy", {}).get("BB_RTR", {}).get("trades", [])
    days = src_data.get("strategy", {}).get("BB_RTR", {}).get("periodic_breakdown", {}).get("day", [])

    # Добавляем в итоговый файл
    result_data["strategy"]["BB_RTR"]["trades"].extend(trades)
    result_data["strategy"]["BB_RTR"]["periodic_breakdown"]["day"].extend(days)

# Сохраняем обновленный result файл
with open("uuuuuu", "w") as out_f:
    json.dump(result_data, out_f, indent=4)

print("✅ Все данные успешно собраны в 'final_result.json'")