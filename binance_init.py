import json
import logging
import os
import time
from datetime import datetime

from binance_api import Binance

with open('config.json', 'r', encoding='utf-8') as fh:
    config = json.load(fh)

if 'api_key' not in config or 'secret_key' not in config:
    raise Exception(
        'Добавьте обязательные глобальные параметры api_key и/или secret_key в config.json')
else:
    bot = Binance(
        API_KEY=config['api_key'],
        SECRET_KEY=config['secret_key']
    )

pairs = config['pairs']

for offset, elem in enumerate(pairs):
    if 'quote' not in pairs[offset] or 'base' not in pairs[offset]:
        raise Exception(
            'Добавьте обязательные локальные параметры quote и/или base для каждой пары в config.json')

    pairs[offset]['interval'] = elem.get('interval', '5m')
    pairs[offset]['macd_fast_period'] = elem.get('macd_fast_period', 12)
    pairs[offset]['macd_slow_period'] = elem.get('macd_slow_period', 26)
    pairs[offset]['macd_signal_period'] = elem.get('macd_signal_period', 9)
    pairs[offset]['dom_offers_amount'] = elem.get('dom_offers_amount', 5)
    pairs[offset]['scalp_min'] = elem.get('scalp_min', 4) + 1
    pairs[offset]['scalp_red'] = elem.get('scalp_red', 2)
    pairs[offset]['scalp_delay'] = elem.get('scalp_delay', .5)
    pairs[offset]['scalp_low_price_markup'] = elem.get('scalp_low_price_markup', .2)
    pairs[offset]['dk_extra_interval'] = elem.get('dk_extra_interval', '15m')
    pairs[offset]['dk_delay'] = elem.get('dk_delay', .5)
    pairs[offset]['dk_low_price_markup'] = elem.get('dk_low_price_markup', .2)
    pairs[offset]['spending_sum'] = elem.get('spending_sum', .5)
    pairs[offset]['profit'] = elem.get('profit', .01)
    pairs[offset]['use_stop_loss'] = elem.get('use_stop_loss', False)
    pairs[offset]['stop_loss'] = elem.get('stop_loss', 2.5)

SPENDIGN_SYSTEM = config.get('spending_system', 'dynamic')

BUY_STRATEGY = config.get('buy_strategy', 'dynamic_klines')

SELL_STRATEGY = config.get('sell_strategy', 'scalping')

BUY_LIFE_TIME_SEC = config.get('buy_life_time_sec', 300)

CLEAR_LOGS = config.get('clear_logs', True)

CLEAR_DB = config.get('clear_db', True)

STOCK_FEE = config.get('stock_fee', .001)

USE_BNB_FEES = config.get('use_bnb_fees', True)

MACD_BULL_PERC = config.get('macd_bull_perc', 30)

MACD_BEAR_PERC = config.get('macd_bear_perc', 70)

STOCHRSI_PERC = config.get('stochris_perc', 50)

# Получаем ограничения торгов по всем парам с биржи
local_time = int(time.time())
limits = bot.exchangeInfo()
server_time = int(limits['serverTime'])//1000


# Функция, которая приводит любое число к числу, кратному шагу, указанному биржей
# Если передать параметр increase=True, то округление произойдет к следующему шагу
def adjust_to_step(value, step, increase=False):
    return ((int(value*100000000) - int(value*100000000) % int(
            float(step)*100000000)) / 100000000) + (float(step) if increase else 0)


# Подключаем логирование
logging.basicConfig(
    format="%(asctime)s [%(levelname)-5.5s] %(message)s",
    level=logging.INFO,
    handlers=[
        logging.FileHandler(
            filename="{path}/logs/{fname}.log".format(
                path=os.path.dirname(os.path.abspath(__file__)), fname="binance"),
            mode='w' if CLEAR_LOGS else 'a'
        ),
        logging.StreamHandler()
    ]
)

log = logging.getLogger('')

shift_seconds = server_time-local_time
bot.set_shift_seconds(shift_seconds)

log.info("""
    Текущее время: {local_time_d} {local_time_u}
    Время сервера: {server_time_d} {server_time_u}
    Разница: {diff:0.8f} {warn}
    Бот будет работать, как будто сейчас: {fake_time_d} {fake_time_u}
""".format(
    local_time_d=datetime.fromtimestamp(local_time),
    local_time_u=local_time,
    server_time_d=datetime.fromtimestamp(server_time),
    server_time_u=server_time,
    diff=abs(local_time-server_time),
    warn="ТЕКУЩЕЕ ВРЕМЯ ВЫШЕ" if local_time > server_time else '',
    fake_time_d=datetime.fromtimestamp(local_time+shift_seconds),
    fake_time_u=local_time+shift_seconds)
)
