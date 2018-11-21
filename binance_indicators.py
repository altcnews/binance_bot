import warnings

import numpy as np
import pandas as pd
import talib as tb

from binance_api import Binance
from binance_init import bot

np.seterr(all='ignore')
warnings.simplefilter(action='ignore', category=FutureWarning)


class Indicators:

    def __init__(self, pair):
        self.pair = pair

    # Функция, реализующая индикатор STOCHASTIC RSI
    def stochrsi_indicator(self, series, period=14, smoothK=3, smoothD=3):
        # Вычисляем RSI
        delta = series.diff().dropna()
        ups = delta * 0
        downs = ups.copy()
        ups[delta > 0] = delta[delta > 0]
        downs[delta < 0] = -delta[delta < 0]
        # First value is sum of avg gains
        ups[ups.index[period-1]] = np.mean(ups[:period])
        ups = ups.drop(ups.index[:(period-1)])
        # First value is sum of avg losses
        downs[downs.index[period-1]] = np.mean(downs[:period])
        downs = downs.drop(downs.index[:(period-1)])
        rs = (ups.ewm(com=period-1, min_periods=0, adjust=False, ignore_na=False).mean() /
              downs.ewm(com=period-1, min_periods=0, adjust=False, ignore_na=False).mean())
        rsi = 100 - 100 / (1 + rs)

        # Вычисляем StochRSI
        stochrsi = ((rsi - rsi.rolling(period).min()) /
                    (rsi.rolling(period).max() - rsi.rolling(period).min()))
        stochrsi_K = stochrsi.rolling(smoothK).mean()
        stochrsi_D = stochrsi_K.rolling(smoothD).mean()

        stochrsi.index = range(len(stochrsi))  # при необходимости можно вернуть
        stochrsi_K.index = range(len(stochrsi_K))
        stochrsi_D.index = range(len(stochrsi_D))

        return stochrsi_K, stochrsi_D

    # Функция, которая с помощью индикатора RSI определяет, когда стоит закупиться
    def stochrsi(self, interval, stochrsi_perc, is_sell=False):
        # Получаем данные с биржи
        klines = bot.klines(
            symbol=self.pair,
            interval=interval,
            limit=300)

        close = pd.Series([float(item[4]) for item in klines])
        stochrsi_K, stochrsi_D = self.stochrsi_indicator(close)

        perc = stochrsi_D.iloc[-1]*100
        activity_time = False

        if is_sell:
            if stochrsi_D.iloc[-1] >= stochrsi_K.iloc[-1] and perc >= stochrsi_perc:
                activity_time = True
        else:
            if stochrsi_D.iloc[-1] >= stochrsi_K.iloc[-1] and perc <= stochrsi_perc:
                activity_time = True

        return activity_time

    # Функция, которая с помощью индикатора MACD определяет, когда стоит закупиться
    def macd(self, interval, fastperiod=12, slowperiod=26, signalperiod=9, bull_perc=30, bear_perc=70):
        # Получаем данные с биржи
        klines = bot.klines(
            symbol=self.pair,
            interval=interval,
            limit=300)

        close = np.asarray([float(item[4]) for item in klines])
        macd, macdsignal, macdhist = tb.MACD(close, fastperiod, slowperiod, signalperiod)

        idx = np.argwhere(np.diff(np.sign(macd - macdsignal)) != 0).reshape(-1) + 0

        max_v = 0

        for offset, elem in enumerate(macdhist):
            activity_time = False
            curr_v = macd[offset] - macdsignal[offset]
            if abs(curr_v) > abs(max_v):
                max_v = curr_v
            perc = curr_v/max_v

            # восходящий тренд
            if ((macd[offset] > macdsignal[offset] and perc*100 > bull_perc) or
                    (macd[offset] < macdsignal[offset] and perc*100 <= (100-bear_perc))):
                activity_time = True

            if offset in idx and not np.isnan(elem):
                # тренд изменился
                max_v = curr_v = 0  # обнуляем пик спреда между линиями

        return activity_time
