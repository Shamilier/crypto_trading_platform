from freqtrade.strategy import IStrategy
from freqtrade.persistence import Trade

class OneTimeBTCBuyStrategy(IStrategy):
    # Интервал свечей
    timeframe = '1m'

    # Ограничение: максимальное количество открытых сделок
    max_open_trades = 1

    # ROI (возврат на инвестиции)
    minimal_roi = {
        "0": 1  # Максимальный ROI: закрывать сделку при +1000% прибыли
    }

    # Стоп-лосс
    stoploss = -0.03  # Максимальная потеря 10%

    # Количество свечей для инициализации
    startup_candle_count = 1

    def __init__(self):
        super().__init__()
        self.has_bought = False  # Флаг, который указывает, была ли уже сделка

    def populate_indicators(self, dataframe, metadata):
        """
        Добавляем необходимые индикаторы. В данном случае индикаторы не нужны, так как логика простая.
        """
        return dataframe

    def populate_entry_trend(self, dataframe, metadata):
        """
        Условия входа в сделку.
        """
        # Устанавливаем значение по умолчанию (нет входа в сделку)
        dataframe['enter_long'] = 0

        # Проверяем, что сделка еще не была совершена
        if self.has_bought:
            return dataframe

        # Условие: цена BTC/USDT > 100,000
        dataframe.loc[
            (dataframe['close'] > 100000),  # Если цена закрытия > $100,000
            'enter_long'
        ] = 1

        return dataframe

    def populate_exit_trend(self, dataframe, metadata):
        """
        Условия выхода из сделки. В данном случае сделка будет закрыта по ROI или стоп-лоссу.
        """
        dataframe['exit_long'] = 0
        return dataframe

    def custom_entry_condition(self, pair):
        """
        Проверяем, была ли уже сделка для данной пары.
        """
        trades = Trade.get_trades(pair=pair, is_open=True)
        if trades:
            self.has_bought = True  # Обновляем флаг, если сделка уже была совершена

    def confirm_trade_entry(self, pair, order_type, amount, rate, time_in_force, stoploss):
        """
        Функция вызывается перед размещением ордера. Устанавливаем флаг после успешной сделки.
        """
        result = super().confirm_trade_entry(pair, order_type, amount, rate, time_in_force, stoploss)
        if result:
            self.has_bought = True  # Устанавливаем флаг после покупки
        return result
