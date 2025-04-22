import json

# Пути к исходным файлам
target_file2 = '/Users/shamilgaliev18mail.ru/cry/ft_userdata/user_data/backtest_results/backtest_today6-2025-04-15_10-43-52.json'  # Путь ко второму файлу
result_file = '/Users/shamilgaliev18mail.ru/cry/ft_userdata/user_data/backtest_results/result_file.json'  # Путь к файлу, куда будем добавлять данные

# Чтение данных из второго файла target_file2
with open(target_file2, 'r') as f:
    target_data2 = json.load(f)

# Извлечение массива сделок из второго файла
trades_from_target_file2 = target_data2.get("strategy", {}).get("E0V1E", {}).get("periodic_breakdown", {}).get("day", [])

# Преобразуем данные во второй файл в нужный формат для добавления в result_file
new_trades = []
for entry in trades_from_target_file2:
    trade_info = {
        "date": entry.get('date'),
        "date_ts": entry.get('date_ts'),
        "profit_abs": entry.get('profit_abs'),
        "wins": entry.get('wins'),
        "draws": entry.get('draws'),
        "losses": entry.get('losses'),
        "trades": entry.get('trades'),
        "profit_factor": entry.get('profit_factor')
    }
    new_trades.append(trade_info)

# Чтение данных из result_file, если файл существует
try:
    with open(result_file, 'r') as f:
        result_data = json.load(f)
except FileNotFoundError:
    result_data = {"trades": []}

# Добавляем новые сделки в существующие
result_data["trades"].extend(new_trades)

# Сохраняем обновленные данные в result_file
with open(result_file, 'w') as f:
    json.dump(result_data, f, indent=4)

print(f"Данные успешно добавлены в {result_file}")