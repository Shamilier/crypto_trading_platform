# pragma pylint: disable=missing-docstring, invalid-name, pointless-string-statement
# flake8: noqa: F401
# isort: skip_file
# --- Do not remove these libs ---
import numpy as np
import pandas as pd
from pandas import DataFrame
from datetime import datetime
from typing import Optional, Union

from freqtrade.strategy import (BooleanParameter, CategoricalParameter, DecimalParameter,
                                IntParameter, IStrategy, merge_informative_pair)

# --------------------------------
# Add your lib to import here
import talib.abstract as ta
import pandas_ta as pta
from technical import qtpylib


class UniversalMACD(IStrategy):
    # By: Masoud Azizi (@mablue)
    # Tradingview Page: https://www.tradingview.com/script/xNEWcB8s-Universal-Moving-Average-Convergence-Divergence/

    # Strategy interface version - allow new iterations of the strategy interface.
    # Check the documentation or the Sample strategy to get the latest version.
    INTERFACE_VERSION = 3

    # Optimal timeframe for the strategy.
    timeframe = '5m'

    # Can this strategy go short?
    can_short: bool = False

    # $ freqtrade hyperopt -s UniversalMACD --hyperopt-loss SharpeHyperOptLossDaily

    # "max_open_trades": 1,
    # "stake_currency": "USDT",
    # "stake_amount": 990,
    # "dry_run_wallet": 1000,
    # "trading_mode": "spot",
    # "XMR/USDT","ATOM/USDT","FTM/USDT","CHR/USDT","BNB/USDT","ALGO/USDT","XEM/USDT","XTZ/USDT","ZEC/USDT","ADA/USDT",
    # "CHZ/USDT","BTT/USDT","LUNA/USDT","VRA/USDT","KSM/USDT","DASH/USDT","COMP/USDT","CRO/USDT","WAVES/USDT","MKR/USDT",
    # "DIA/USDT","LINK/USDT","DOT/USDT","YFI/USDT","UNI/USDT","FIL/USDT","AAVE/USDT","KCS/USDT","LTC/USDT","BSV/USDT",
    # "XLM/USDT","ETC/USDT","ETH/USDT","BTC/USDT","XRP/USDT","TRX/USDT","VET/USDT","NEO/USDT","EOS/USDT","BCH/USDT",
    # "CRV/USDT","SUSHI/USDT","KLV/USDT","DOGE/USDT","CAKE/USDT","AVAX/USDT","MANA/USDT","SAND/USDT","SHIB/USDT",
    # "KDA/USDT","ICP/USDT","MATIC/USDT","ELON/USDT","NFT/USDT","ARRR/USDT","NEAR/USDT","CLV/USDT","SOL/USDT","SLP/USDT",
    # "XPR/USDT","DYDX/USDT","FTT/USDT","KAVA/USDT","XEC/USDT"
    # "method": "StaticPairList"

    # *16 / 100: 40    trades.
    # 31 / 9 / 0    Wins / Draws / Losses.
    # Avg    profit    2.34 %.
    # Median    profit    3.00 %.
    # Total    profit    928.95036811    USDT(92.90 %).
    # Avg    duration    3: 13:00    min.\
    # Objective: -11.63412

    minimal_roi = {
        "0": 0.275,
        "31": 0.098,
        "88": 0.038,
        "205": 0
    }

    # Stoploss:
    stoploss = -0.151




    # minimal_roi = {
    #     "0": 0.154,
    #     "15": 0.08,
    #     "43": 0.034,
    #     "110": 0
    # }

    # # Stoploss:
    # stoploss = -0.231


    # Trailing stop:
    trailing_stop = False  # value loaded from strategy
    trailing_stop_positive = None  # value loaded from strategy
    trailing_stop_positive_offset = 0.0  # value loaded from strategy
    trailing_only_offset_is_reached = False  # value loaded from strategy

    # Number of candles the strategy requires before producing valid signals
    startup_candle_count: int = 30

    # Strategy parameters
    buy_umacd_max = DecimalParameter(-0.05, 0.05, decimals=5, default=-0.01176, space="buy")
    buy_umacd_min = DecimalParameter(-0.05, 0.05, decimals=5, default=-0.01416, space="buy")
    sell_umacd_max = DecimalParameter(-0.05, 0.05, decimals=5, default=-0.02323, space="sell")
    sell_umacd_min = DecimalParameter(-0.05, 0.05, decimals=5, default=-0.00707, space="sell")


    def leverage(self, pair: str, current_time: datetime, current_rate: float,
                 proposed_leverage: float, max_leverage: float, entry_tag: str | None, side: str,
                 **kwargs) -> float:
        """
        Customize leverage for each new trade. This method is only called in futures mode.

        :param pair: Pair that's currently analyzed
        :param current_time: datetime object, containing the current datetime
        :param current_rate: Rate, calculated based on pricing settings in exit_pricing.
        :param proposed_leverage: A leverage proposed by the bot.
        :param max_leverage: Max leverage allowed on this pair
        :param entry_tag: Optional entry_tag (buy_tag) if provided with the buy signal.
        :param side: "long" or "short" - indicating the direction of the proposed trade
        :return: A leverage amount, which is between 1.0 and max_leverage.
        """
        return 5.0


    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe['ma12'] = ta.EMA(dataframe, timeperiod=12)
        dataframe['ma26'] = ta.EMA(dataframe, timeperiod=26)
        dataframe['umacd'] = (dataframe['ma12'] / dataframe['ma26']) - 1

        # Just for show user the min and max of indicator in different coins to set inside hyperoptable variables.cuz
        # in different timeframes should change the min and max in hyperoptable variables.
        # print(dataframe['umacd'].min(), dataframe['umacd'].max())

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe.loc[
            (
                (dataframe['umacd'].between(self.buy_umacd_min.value, self.buy_umacd_max.value))

            ),
            'enter_long'] = 1

        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe.loc[
            (
                (dataframe['umacd'].between(self.sell_umacd_min.value, self.sell_umacd_max.value))
            ),
            'exit_long'] = 1

        return dataframe
