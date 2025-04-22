# BuyEveryThirtySeconds.py
# pragma pylint: disable=missing-docstring, invalid-name, pointless-string-statement
# flake8: noqa: F401
# isort: skip_file

import numpy as np
import pandas as pd
from datetime import datetime
from pandas import DataFrame
from freqtrade.strategy import IStrategy

class every_minute(IStrategy):
    """
    Стратегия для теста: генерирует сигнал на покупку на каждой свече.
    Это позволит проверить вызов функции "Текущие позиции".
    """
    # Если ваш источник данных поддерживает субминутные свечи, можно попробовать '30s'
    timeframe = '1m'  # Если возможно, поменяйте на '30s'
    startup_candle_count: int = 1
    can_short: bool = False

    # Настройки minimal_roi и stoploss задаем так, чтобы стратегия не продавала автоматически
    minimal_roi = {
        "0": 10  # 1000% ROI – фактически никогда не срабатывает
    }
    stoploss = -0.99  # Максимально допустимый стоплосс для теста
    trailing_stop = False

    # Разрешаем несколько открытых сделок для тестирования
    max_open_trades = 10

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # В этой стратегии индикаторы не требуются
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # Генерируем сигнал на вход на каждой свече
        dataframe.loc[:, 'enter_long'] = 1
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # Выходы не формируются автоматически (для теста)
        dataframe.loc[:, 'exit_long'] = 0
        return dataframe