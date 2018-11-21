#!/usr/bin/env python3
import time
from datetime import datetime

from binance_init import *
from binance_queries import Db_Queries
from binance_strategies import Buy_Strategies, Sell_Strategies


def sell():
    log.info("""
        Ордер {order} выполнен, получено {exec_qty:0.8f}.
        Создаем ордер на продажу
    """.format(
            order=order,
            exec_qty=float(stock_order_data['executedQty']))
    )

    # Смотрим, какие ограничения есть для создания ордера на продажу
    for elem in limits['symbols']:
        if elem['symbol'] == orders_info[order]['order_pair']:
            CURR_LIMITS = elem
            break
    else:
        raise Exception("Не удалось найти настройки выбранной пары "+orders_info[order]['order_pair'])

    # Рассчитываем данные для ордера на продажу

    # Имеющееся кол-во на продажу
    has_amount = orders_info[order]['buy_amount'] * ((1-STOCK_FEE) if not USE_BNB_FEES else 1)
    # Приводим количество на продажу к числу, кратному по ограничению
    sell_amount = adjust_to_step(has_amount, CURR_LIMITS['filters'][1]['stepSize'])
    # Рассчитываем минимальную сумму, которую нужно получить, чтобы остаться в плюсе
    need_to_earn = (
        orders_info[order]['buy_amount'] *
        orders_info[order]['buy_price'] *
        (1+all_pairs[stock_order_data['symbol']]['profit'])
    )
    # Рассчитываем минимальную цену для продажи
    min_price = (need_to_earn/sell_amount) / ((1-STOCK_FEE) if not USE_BNB_FEES else 1)
    # Приводим к нужному виду. Если цена после срезки лишних символов меньше нужной, увеличиваем на шаг
    cut_price = max(
        adjust_to_step(min_price, CURR_LIMITS['filters'][0]['tickSize'], increase=True),
        adjust_to_step(min_price, CURR_LIMITS['filters'][0]['tickSize'])
    )
    
    sell_strategies = Sell_Strategies(cut_price, orders_info[order]['order_pair'], all_pairs[stock_order_data['symbol']])
    # Выбор sell-стратегии SCALPING или DOM
    if SELL_STRATEGY == 'scalping':
        need_price, curr_rate = sell_strategies.scalping()
    elif SELL_STRATEGY == 'dom':
        need_price, curr_rate = sell_strategies.dom()

    log.info("""
        Изначально было куплено {buy_initial:0.8f}, за вычетом комиссии {has_amount:0.8f},
        Получится продать только {sell_amount:0.8f}
        Нужно получить как минимум {need_to_earn:0.8f} {curr}
        Мин. цена (с комиссией) составит {min_price}, после приведения {cut_price:0.8f}
        Текущая цена рынка {curr_rate:0.8f}
        Итоговая цена продажи: {need_price:0.8f}
    """.format(
            buy_initial=orders_info[order]['buy_amount'],
            has_amount=has_amount,
            sell_amount=sell_amount,
            need_to_earn=need_to_earn,
            curr=all_pairs[orders_info[order]['order_pair']]['quote'],
            min_price=min_price,
            cut_price=cut_price,
            need_price=need_price,
            curr_rate=curr_rate)
    )

    # Если итоговая сумма продажи меньше минимума, ругаемся и не продаем
    if (need_price*has_amount) < float(CURR_LIMITS['filters'][2]['minNotional']):
        raise Exception("""
            Итоговый размер сделки {trade_am:0.8f} меньше допустимого по паре {min_am:0.8f}. """.format(
                trade_am=(need_price*has_amount),
                min_am=float(CURR_LIMITS['filters'][2]['minNotional']))
        )

    log.info(
        'Рассчитан ордер на продажу: кол-во {amount:0.8f}, курс: {rate:0.8f}'.format(amount=sell_amount, rate=need_price))

    # Отправляем команду на создание ордера с рассчитанными параметрами
    new_order = bot.createOrder(
        symbol=orders_info[order]['order_pair'],
        recvWindow=5000,
        side='SELL',
        type='LIMIT',
        timeInForce='GTC',  # Good Till Cancel
        quantity="{quantity:0.{precision}f}".format(quantity=sell_amount, precision=CURR_LIMITS['baseAssetPrecision']),
        price="{price:0.{precision}f}".format(price=need_price, precision=CURR_LIMITS['baseAssetPrecision']),
        newOrderRespType='FULL'
    )
    # Если ордер создался без ошибок, записываем данные в базу данных
    if 'orderId' in new_order:
        log.info("Создан ордер на продажу {new_order}".format(new_order=new_order))
        queries.insert_sell_order(order, new_order, sell_amount, need_price)
    # Если были ошибки при создании, выводим сообщение
    else:
        log.warning("Не удалось создать ордер на продажу {new_order}".format(new_order=new_order))


def buy():
    log.info("Работаем с парой {pair}".format(pair=pair_name))

    # Получаем лимиты пары с биржи
    for elem in limits['symbols']:
        if elem['symbol'] == pair_name:
            CURR_LIMITS = elem
            break
    else:
        raise Exception("Не удалось найти настройки выбранной пары " + pair_name)

    # Получаем балансы с биржи по указанным валютам
    balances = {
        balance['asset']: float(balance['free']) for balance in bot.account()['balances']
        if balance['asset'] in [pair_obj['quote'], pair_obj['base']]
    }
    log.info(
        "Баланс {balance}".format(balance=["{k}:{bal:0.8f}".format(k=k, bal=balances[k]) for k in balances]))
    # Если баланс позволяет торговать - выше лимитов биржи и выше указанной суммы в настройках
    if ((SPENDIGN_SYSTEM == 'fixed' and balances[pair_obj['quote']] >= pair_obj['spending_sum']) or
        (SPENDIGN_SYSTEM == 'dynamic' and pair_obj['spending_sum'] <= 1)):

        strategy = Buy_Strategies(pair_name, pair_obj, CURR_LIMITS)
        # Выбор buy-стратегии SCALPING или DOM
        if BUY_STRATEGY == 'scalping':
            my_need_price = strategy.scalping()
        elif BUY_STRATEGY == 'dom':
            my_need_price = strategy.dom()
        elif BUY_STRATEGY == 'dynamic_klines':
            my_need_price = strategy.dynamic_klines()

        # Рассчитываем кол-во, которое можно купить, и тоже приводим его к кратному значению
        if SPENDIGN_SYSTEM == 'fixed':
            my_amount = adjust_to_step(pair_obj['spending_sum']/my_need_price, CURR_LIMITS['filters'][1]['stepSize'])
        else:
            my_amount = adjust_to_step(
                pair_obj['spending_sum']*balances[pair_obj['quote']]/my_need_price,
                CURR_LIMITS['filters'][1]['stepSize']
            )

        # Если в итоге получается объем торгов меньше минимально разрешенного, то ругаемся и не создаем ордер
        if my_amount < float(CURR_LIMITS['filters'][1]['stepSize']) or my_amount < float(CURR_LIMITS['filters'][1]['minQty']):
            raise Exception("""
                Минимальная сумма лота: {min_lot:0.8f}
                Минимальный шаг лота: {min_lot_step:0.8f}
                На свои деньги мы могли бы купить {wanted_amount:0.8f}
                После приведения к минимальному шагу мы можем купить {my_amount:0.8f}
                Покупка невозможна, выход. Увеличьте размер ставки
            """.format(
                    wanted_amount=pair_obj['spending_sum'] /
                        my_need_price if SPENDIGN_SYSTEM == 'fixed' else pair_obj['spending_sum'] *
                        balances[pair_obj['quote']] /
                        my_need_price,
                    my_amount=my_amount,
                    min_lot=float(CURR_LIMITS['filters'][1]['minQty']),
                    min_lot_step=float(CURR_LIMITS['filters'][1]['stepSize'])
                )
            )

        # Итоговый размер лота
        trade_am = my_need_price*my_amount
        log.info("""
            Цена {need_price:0.8f},
            объем после приведения {my_amount:0.8f},
            итоговый размер сделки {trade_am:0.8f}
        """.format(
                need_price=my_need_price,
                my_amount=my_amount,
                trade_am=trade_am
            )
        )
        # Если итоговый размер лота меньше минимального разрешенного, то ругаемся и не создаем ордер
        if trade_am < float(CURR_LIMITS['filters'][2]['minNotional']):
            raise Exception("""
                Итоговый размер сделки {trade_am:0.8f} меньше допустимого по паре {min_am:0.8f}.
                Увеличьте сумму торгов (в {incr} раз(а))
            """.format(
                    trade_am=trade_am,
                    min_am=float(CURR_LIMITS['filters'][2]['minNotional']),
                    incr=float(CURR_LIMITS['filters'][2]['minNotional'])/trade_am
                )
            )
        log.info(
            'Рассчитан ордер на покупку: кол-во {amount:0.8f}, курс: {rate:0.8f}'.format(amount=my_amount, rate=my_need_price))
        # Отправляем команду на биржу о создании ордера на покупку с рассчитанными параметрами
        new_order = bot.createOrder(
            symbol=pair_name,
            recvWindow=5000,
            side='BUY',
            type='LIMIT',
            timeInForce='GTC',  # Good Till Cancel
            quantity="{quantity:0.{precision}f}".format(
                quantity=my_amount,
                precision=CURR_LIMITS['baseAssetPrecision']
            ),
            price="{price:0.{precision}f}".format(
                price=my_need_price,
                precision=CURR_LIMITS['baseAssetPrecision']
            ),
            newOrderRespType='FULL'
        )
        # Если удалось создать ордер на покупку, записываем информацию в БД
        if 'orderId' in new_order:
            log.info("Создан ордер на покупку {new_order}".format(new_order=new_order))
            queries.insert_buy_order(pair_name, new_order, my_amount, my_need_price)
        else:
            log.warning(
                "Не удалось создать ордер на покупку! {new_order}".format(new_order=str(new_order)))

    else:
        log.warning(
            'Для создания ордера на покупку нужна сумма ({curr}), не превышающая ваш бюджет, выход'.format(curr=pair_obj['quote']))


def check_cancel():
    order_created = int(orders_info[order]['buy_created'])
    time_passed = int(time.time())-order_created
    log.info("Прошло времени после создания {passed:0.2f}".format(passed=time_passed))
    # Прошло больше времени, чем разрешено держать ордер
    if time_passed > BUY_LIFE_TIME_SEC:
        log.info(
            """Ордер {order} пора отменять, прошло {passed:0.1f} сек.""".format(order=order, passed=time_passed)
        )
        # Отменяем ордер на бирже
        cancel = bot.cancelOrder(
            symbol=orders_info[order]['order_pair'],
            orderId=order
        )
        # Если удалось отменить ордер, скидываем информацию в БД
        if 'orderId' in cancel:
            log.info("Ордер {order} был успешно отменен".format(order=order))
            queries.update_cancel_order(order)
        else:
            log.warning("Не удалось отменить ордер: {cancel}".format(cancel=cancel))


def sell_on_market():
    curr_rate = float(bot.tickerPrice(symbol=orders_info[order]['order_pair'])['price'])

    if (1-curr_rate/orders_info[order]['buy_price']) * 100 >= all_pairs[orders_info[order]['order_pair']]['stop_loss']:
        log.info("{pair} Цена упала до стоплосс (покупали по {b:0.8f}, сейчас {s:0.8f}), пора продавать".format(
                pair=orders_info[order]['order_pair'],
                b=orders_info[order]['buy_price'],
                s=curr_rate)
        )
        # Отменяем ордер на бирже
        cancel = bot.cancelOrder(
            symbol=orders_info[order]['order_pair'],
            orderId=order)
        # Если удалось отменить ордер, скидываем информацию в БД
        if 'orderId' in cancel:
            log.info("Ордер {order} был успешно отменен, продаем по рынку".format(order=order))
            new_order = bot.createOrder(
                symbol=orders_info[order]['order_pair'],
                recvWindow=15000,
                side='SELL',
                type='MARKET',
                quantity=orders_info[order]['sell_amount'])
            if not new_order.get('code'):
                log.info("Создан ордер на продажу по рынку " + str(new_order))
                queries.delete_sell_order(order)
        else:
            log.warning("Не удалось отменить ордер: {cancel}".format(cancel=cancel))
    else:
        log.info("{pair} (покупали по {b:0.8f}, сейчас {s:0.8f}), расхождение {sl:0.4f}%, panic_sell = {ps:0.4f}% ({ps_rate:0.8f}), продажа с профитом: {tp:0.8f}".format(
                pair=orders_info[order]['order_pair'],
                b=orders_info[order]['buy_price'],
                s=curr_rate,
                sl=(1-curr_rate/orders_info[order]['buy_price']) * 100,
                ps=all_pairs[orders_info[order]['order_pair']]['stop_loss'],
                ps_rate=orders_info[order]['buy_price']/100 * (100-all_pairs[orders_info[order]['order_pair']]['stop_loss']),
                tp=orders_info[order]['sell_price'])
        )


def resell_on_market():
    # На случай, если после отмены произошел разрыв связи
    new_order = bot.createOrder(
        symbol=orders_info[order]['order_pair'],
        recvWindow=15000,
        side='SELL',
        type='MARKET',
        quantity=orders_info[order]['sell_amount'],
    )
    if not new_order.get('code'):
        log.info("Создан ордер на продажу по рынку " + str(new_order))
        queries.delete_sell_order(order)


def update_filled_sell():
    log.info("Ордер {order} на продажу исполнен".format(order=order))
    queries.update_sell_order(order)


queries = Db_Queries()
queries.clear_db()
queries.create_order_table()
# Бесконечный цикл программы
try:
    while True:
        log.info("Получаем все неисполненные ордера по БД")

        orders_info = queries.select_unfilled_orders()
        # Формируем словарь из указанных пар для удобного доступа
        all_pairs = {
            pair['base'].upper() + pair['quote'].upper(): pair for pair in pairs}

        if orders_info:
            log.info(
                "Получены неисполненные ордера из БД: {orders}".format(
                    orders=[(order, orders_info[order]['order_pair']) for order in orders_info])
            )

            # Проверяем каждый неисполненный по базе ордер
            for order in orders_info:
                # Получаем по ордеру последнюю информацию по бирже
                stock_order_data = bot.orderInfo(symbol=orders_info[order]['order_pair'], orderId=order)
                order_status = stock_order_data['status']

                log.info(
                    "Состояние ордера {order} - {status}".format(order=order, status=order_status))
                if order_status == 'NEW':
                    log.info('Ордер {order} всё еще не выполнен'.format(order=order))

                # Если ордер на покупку
                if orders_info[order]['order_type'] == 'buy':
                    # Если ордер уже исполнен
                    if order_status == 'FILLED':
                        sell()
                    # Ордер еще не исполнен, частичного исполнения нет, проверяем возможность отмены
                    elif order_status == 'NEW':
                        check_cancel()
                    elif order_status == 'PARTIALLY_FILLED':
                        log.info("Ордер {order} частично исполнен, ждем завершения".format(order=order))

                # Если это ордер на продажу, и он исполнен
                if order_status == 'FILLED' and orders_info[order]['order_type'] == 'sell':
                    update_filled_sell()

                if all_pairs[orders_info[order]['order_pair']]['use_stop_loss']:
                    if order_status == 'NEW' and orders_info[order]['order_type'] == 'sell':
                        sell_on_market()
                    elif order_status == 'CANCELED' and orders_info[order]['order_type'] == 'sell':
                        resell_on_market()
        else:
            log.info("Неисполненных ордеров в БД нет")

        log.info('Получаем из настроек все пары, по которым нет неисполненных ордеров')

        all_pairs = queries.select_filled_pairs(all_pairs)

        # Если остались пары, по которым нет текущих торгов
        if all_pairs:
            log.info(
                'Найдены пары, по которым нет неисполненных ордеров: {pairs}'.format(pairs=list(all_pairs.keys())))
            for pair_name, pair_obj in all_pairs.items():
                buy()
        else:
            log.info('По всем парам есть неисполненные ордера')

except Exception as e:
    log.exception(e)
finally:
    queries.close_conn()
