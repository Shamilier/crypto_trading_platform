from freqtrade.strategy import IStrategy
from typing import Dict, List
from functools import reduce
from pandas import DataFrame
import talib.abstract as ta
import freqtrade.vendor.qtpylib.indicators as qtpylib

class ScalpFutures2(IStrategy):
    INTERFACE_VERSION: int = 3
    minimal_roi = {
        "0": 0.2
    }
    stoploss = -0.1
    timeframe = '1m'
    # Добавление trailing stop в настройки стратегии
    trailing_stop = True
    trailing_stop_positive = 0.001
    trailing_stop_positive_offset = 0.0015

    trailing_only_offset_is_reached = True
    
    def get_leverage(self, pair: str):
        # Словарь левериджа из конфига
        leverages = self.config['leverage']['leverages']
        # Возвращаем леверидж для пары, если он есть, или дефолтное значение
        return leverages.get(pair, leverages.get('__default__', 10))

    
    def custom_stake_amount(self, pair: str, current_time, current_rate: float,
                        proposed_stake: float, min_stake, max_stake: float,
                        leverage: float, entry_tag, side: str,
                        **kwargs) -> float:
        leverage = self.get_leverage(pair)
        return proposed_stake * leverage


    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # Увеличиваем периоды EMA
        dataframe['ema_high'] = ta.EMA(dataframe, timeperiod=10, price='high')
        dataframe['ema_close'] = ta.EMA(dataframe, timeperiod=10, price='close')
        dataframe['ema_low'] = ta.EMA(dataframe, timeperiod=10, price='low')

        stoch_fast = ta.STOCHF(dataframe, 5, 3, 0, 3, 0)
        dataframe['fastd'] = stoch_fast['fastd']
        dataframe['fastk'] = stoch_fast['fastk']
        dataframe['adx'] = ta.ADX(dataframe)

        bollinger = qtpylib.bollinger_bands(dataframe['close'], window=20, stds=2)
        dataframe['bb_lowerband'] = bollinger['lower']
        dataframe['bb_upperband'] = bollinger['upper']
        dataframe['bb_middleband'] = bollinger['mid']
        
        dataframe['rsi'] = ta.RSI(dataframe, timeperiod=14)
        
        # Добавляем ATR для фильтрации входов
        dataframe['atr'] = ta.ATR(dataframe, timeperiod=14)


        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # Long conditions
                
        dataframe.loc[
            (
                (dataframe['open'] < dataframe['ema_low']) &
                (dataframe['atr'] > dataframe['close'] * 0.0011) &
                (dataframe['adx'] > 30) &
                ((dataframe['fastk'] < 30) & (dataframe['fastd'] < 30) &
                (qtpylib.crossed_above(dataframe['fastk'], dataframe['fastd']))
                )
            ),
            'enter_long'] = 1

        # Short conditions
        dataframe.loc[
        (
            (dataframe['open'] >= dataframe['ema_high']) &
            (dataframe['adx'] > 22) &  # Снижаем порог ADX
            ((dataframe['fastk'] > 70) & (dataframe['fastd'] > 70) &
            (dataframe['rsi'] > 70) &  # RSI показывает перекупленность
            (qtpylib.crossed_below(dataframe['fastk'], dataframe['fastd']))
            )
        ),
        'enter_short'] = 1
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # Exit long positions
        dataframe.loc[
            (
                (dataframe['open'] >= dataframe['ema_high'])
            ) &
            (
                (qtpylib.crossed_above(dataframe['fastk'], 70)) |
                (qtpylib.crossed_above(dataframe['fastd'], 70))
            ),
            'exit_long'] = 1

        # Exit short positions
        dataframe.loc[
            (
                (dataframe['open'] <= dataframe['ema_low'])
            ) &
            (
                (qtpylib.crossed_below(dataframe['fastk'], 30)) |
                (qtpylib.crossed_below(dataframe['fastd'], 30))
            ),
            'exit_short'] = 1
        return dataframe
