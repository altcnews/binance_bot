import time

from binance_indicators import Indicators
from binance_init import (MACD_BEAR_PERC, MACD_BULL_PERC, STOCHRSI_PERC,
                          adjust_to_step, bot, log)


class Buy_Strategies:

    def __init__(self, pair_name, pair_obj, curr_limits):
        self.pair_name = pair_name
        self.pair_obj = pair_obj
        self.indicators = Indicators(pair_name)
        self.curr_limits = curr_limits

    def scalping(self):
        log.info('Ожидаем благоприятную ситуацию для закупки\n')
        while True:
            klines = bot.klines(
                symbol=self.pair_name,
                interval=self.pair_obj['interval'],
                limit=1000)

            last_kline = klines[-1]
            current_low_price = float(last_kline[3])
            current_high_price = float(last_kline[2])

            if self.pair_obj['scalp_min'] == 0:
                min_condition = True
            else:
                lowest_price = min([float(kline[3]) for kline in klines]
                                   [-self.pair_obj['scalp_min']:-1])
                min_condition = current_low_price <= lowest_price

            if self.pair_obj['scalp_red'] == 0:
                red_condition = True
            else:
                red_klines = [float(kline[4]) < float(kline[1])
                              for kline in klines[-self.pair_obj['scalp_red']:]]
                red_condition = False not in red_klines

            kline_part_time = int(
                last_kline[0] + (last_kline[6]-last_kline[0])*self.pair_obj['scalp_delay']) // 1000
            current_time = int(time.time())
            time_condition = current_time > kline_part_time

            macd_condition = self.indicators.macd(
                self.pair_obj['interval'],
                self.pair_obj['macd_fast_period'],
                self.pair_obj['macd_slow_period'],
                self.pair_obj['macd_signal_period'],
                MACD_BULL_PERC, MACD_BEAR_PERC)

            stochrsi_condition = self.indicators.stochrsi(self.pair_obj['interval'], STOCHRSI_PERC)

            condition_messages = []
            if min_condition:
                condition_messages.append('Условие scalp_min соблюдено')
            else:
                condition_messages.append('Условие scalp_min не соблюдено')
            if red_condition:
                condition_messages.append('Условие scalp_red соблюдено')
            else:
                condition_messages.append('Условие scalp_red не соблюдено')
            if time_condition:
                condition_messages.append('Условие scalp_delay соблюдено')
            else:
                condition_messages.append('Условие scalp_delay не соблюдено')
            if macd_condition:
                condition_messages.append('Условия индикатора MACD соблюдены')
            else:
                condition_messages.append('Условия индикатора MACD не соблюдены')
            if stochrsi_condition:
                condition_messages.append('Условия индикатора Stochastic RSI соблюдены')
            else:
                condition_messages.append('Условия индикатора Stochastic RSI не соблюдены')

            if min_condition and red_condition and time_condition and macd_condition and stochrsi_condition:
                log.info('На рынке благоприятная ситуация. Готовимся к созданию ордера')
                min_price_with_markup = (
                    current_low_price + (current_high_price-current_low_price)*self.pair_obj['scalp_low_price_markup'])
                my_need_price = adjust_to_step(
                    min_price_with_markup, self.curr_limits['filters'][0]['tickSize'])
                return my_need_price
            else:
                log.info('Пара {0}\n    {1}\n    {2}\n    {3}\n    {4}\n    {5}\n'.format(
                    self.pair_name, condition_messages[0], condition_messages[1],
                    condition_messages[2], condition_messages[3], condition_messages[4]))
                continue

    def dom(self):
        offers = bot.depth(
            symbol=self.pair_name,
            limit=self.pair_obj['dom_offers_amount'])
        prices = [float(bid[0]) for bid in offers['bids']]

        try:
            avg_price = sum(prices)/len(prices)
            my_need_price = adjust_to_step(
                avg_price, self.curr_limits['filters'][0]['tickSize'])
            return my_need_price
        except ZeroDivisionError:
            log.info(
                'Не удается вычислить среднюю цену: {prices}'.format(prices=str(prices)))

    def dynamic_klines(self):
        log.info('Ожидаем благоприятную ситуацию для закупки\n')
        while True:
            curr_price = float(bot.tickerPrice(symbol=self.pair_name)['price'])
            klines = bot.klines(
                symbol=self.pair_name,
                interval=self.pair_obj['interval'],
                limit=1000)

            last_kline = klines[-1]
            second_kline = klines[-2]
            third_kline = klines[-3]
            curr_low_price = float(last_kline[3])
            curr_high_price = float(last_kline[2])

            delay = int(
                last_kline[0] + (last_kline[6]-last_kline[0])*self.pair_obj['dk_delay']) // 1000
            curr_time = int(time.time())
            delay_condition = curr_time > delay

            turn_condition = (float(last_kline[3]) > float(second_kline[3])) and (
                float(second_kline[3]) < float(third_kline[3]))
            main_stochrsi_condition = self.indicators.stochrsi(
                self.pair_obj['interval'], STOCHRSI_PERC)
            extra_stochrsi_condition = self.indicators.stochrsi(
                self.pair_obj['dk_extra_interval'], STOCHRSI_PERC)

            macd_condition = self.indicators.macd(
                self.pair_obj['interval'],
                self.pair_obj['macd_fast_period'],
                self.pair_obj['macd_slow_period'],
                self.pair_obj['macd_signal_period'],
                MACD_BULL_PERC, MACD_BEAR_PERC)

            open_less_curr_condition = curr_price < float(second_kline[1])

            condition_messages = []
            if turn_condition:
                condition_messages.append(
                    'Условие разворота рынка соблюдено')
            else:
                condition_messages.append(
                    'Условие разворота рынка не соблюдено')
            if open_less_curr_condition:
                condition_messages.append(
                    'Условие current_prcie < second_open_price соблюдено')
            else:
                condition_messages.append(
                    'Условие current_prcie < second_open_price не соблюдено')
            if delay_condition:
                condition_messages.append(
                    'Условие dk_delay соблюдено')
            else:
                condition_messages.append(
                    'Условие dk_delay не соблюдено')
            if macd_condition:
                condition_messages.append(
                    'Условия индикатора MACD соблюдены')
            else:
                condition_messages.append(
                    'Условия индикатора MACD не соблюдены')
            if main_stochrsi_condition:
                condition_messages.append(
                    'Условия индикатора Stochastic RSI на {}-интервале соблюдены'.format(self.pair_obj['interval']))
            else:
                condition_messages.append(
                    'Условия индикатора Stochastic RSI на {}-интервале не соблюдены'.format(self.pair_obj['interval']))
            if extra_stochrsi_condition:
                condition_messages.append(
                    'Условия индикатора Stochastic RSI на {}-интервале соблюдены'.format(self.pair_obj['dk_extra_interval']))
            else:
                condition_messages.append(
                    'Условия индикатора Stochastic RSI на {}-интервале не соблюдены'.format(self.pair_obj['dk_extra_interval']))

            if turn_condition and open_less_curr_condition and delay_condition and macd_condition and main_stochrsi_condition and extra_stochrsi_condition:
                log.info('На рынке благоприятная ситуация. Готовимся к созданию ордера')
                min_price_with_markup = (
                    curr_low_price + (curr_high_price-curr_low_price)*self.pair_obj['dk_low_price_markup'])
                my_need_price = adjust_to_step(
                    min_price_with_markup, self.curr_limits['filters'][0]['tickSize'])
                return my_need_price
            else:
                log.info('Пара {0}\n    {1}\n    {2}\n    {3}\n    {4}\n    {5}\n    {6}\n'.format(
                    self.pair_name, condition_messages[0], condition_messages[1],
                    condition_messages[2], condition_messages[3], condition_messages[4], condition_messages[5]))


class Sell_Strategies:

    def __init__(self, cut_price, pair_name, pair_obj):
        self.cut_price = cut_price
        self.pair_name = pair_name
        self.pair_obj = pair_obj

    def scalping(self):
        log.info('Ожидаем благоприятную ситуацию для продажи\n')
        indicators = Indicators(self.pair_name)
        ready_to_check = False
        log.info('Ожидаем бычьего тренда и перекупленности более 55%...')
        while True:
            macd_condition = indicators.macd(
                self.pair_obj['interval'],
                self.pair_obj['macd_fast_period'],
                self.pair_obj['macd_slow_period'],
                self.pair_obj['macd_signal_period'], 0, 100)

            stochrsi_condition = indicators.stochrsi(self.pair_obj['interval'], 55, True)

            if macd_condition and stochrsi_condition:
                ready_to_check = True

            klines = bot.klines(
                symbol=self.pair_name,
                interval=self.pair_obj['interval'],
                limit=2)

            last_kline = klines[-1]
            second_kline = klines[-2]

            max_condition = float(last_kline[2]) > float(second_kline[2])

            condition_messages = []
            if macd_condition:
                condition_messages.append(
                    'Рынок БЫЧИЙ. Условие соблюдено')
            else:
                condition_messages.append(
                    'Рынок МЕДВЕЖИЙ. Условие не соблюдено')
            if stochrsi_condition:
                condition_messages.append(
                    'Рынок перекуплен БОЛЕЕ чем на 55%. Условие соблюдено')
            else:
                condition_messages.append(
                    'Рынок перекуплен МЕНЕЕ чем на 55%. Условие не соблюдено')
            if max_condition:
                condition_messages.append(
                    'high price текущей свечи ВЫШЕ, чем high price предыдущей. Условие соблюдено')
            else:
                condition_messages.append(
                    'high price текущей свечи НИЖЕ, чем high price предыдущей. Условие не соблюдено')

            if not ready_to_check:
                continue
            elif macd_condition and stochrsi_condition and max_condition:
                log.info('Все условия соблюдены. Ожидаем ещё более благоприятной ситуации\n')
                continue
            else:
                kline_delay = int(
                    last_kline[0] + (last_kline[6]-last_kline[0])*0.5) // 1000
                current_time = int(time.time())
                time_condition = current_time > kline_delay

                if time_condition:
                    curr_rate = float(bot.tickerPrice(symbol=self.pair_name)['price'])
                    if curr_rate > self.cut_price:
                        log.info('На рынке благоприятная ситуация. Готовимся к созданию ордера')
                        need_price = curr_rate-curr_rate*0.00005
                        return need_price, curr_rate
                    else:
                        log.info(
                            'Ситуация на рынке меняется в худшую сторону. Создаём ордер по минимальному профиту')
                        need_price = self.cut_price
                        return need_price, curr_rate
                else:
                    log.info('Пара {0}\n    {1}\n    {2}\n    {3}\nОжидаем окончания свечи...\n'.format(
                        self.pair_name, condition_messages[0], condition_messages[1], condition_messages[2]))
                    continue

    def dom(self):
        curr_rate = float(bot.tickerPrice(symbol=self.pair_name)['price'])
        need_price = max(self.cut_price, curr_rate)

        return need_price, curr_rate


if __name__ == "__main__":
    pair_obj = {
        'interval': '5m',
        'macd_fast_period': 12,
        'macd_slow_period': 26,
        'macd_signal_period': 9
    }
    sell_strategies = Sell_Strategies(0.087085, 'BCCBTC', pair_obj)
    result = sell_strategies.scalping()
    print(result)
