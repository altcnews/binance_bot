import sqlite3

from binance_init import CLEAR_DB


class Db_Queries:

    def __init__(self):
        # Устанавливаем соединение с локальной базой данных
        self.conn = sqlite3.connect('binance.db')
        self.cursor = self.conn.cursor()

    def clear_db(self):
        if CLEAR_DB:
            orders_q = """
                DROP TABLE IF EXISTS orders;
            """
            self.cursor.execute(orders_q)

    def create_order_table(self):
        # Если не существует таблиц, их нужно создать (первый запуск)
        orders_q = """
            CREATE TABLE IF NOT EXISTS
                orders(
                    order_type TEXT,
                    order_pair TEXT,
                    buy_order_id NUMERIC,
                    buy_amount REAL,
                    buy_price REAL,
                    buy_created DATETIME,
                    buy_finished DATETIME NULL,
                    buy_cancelled DATETIME NULL,
                    sell_order_id NUMERIC NULL,
                    sell_amount REAL NULL,
                    sell_price REAL NULL,
                    sell_created DATETIME NULL,
                    sell_finished DATETIME NULL,
                    force_sell INT DEFAULT 0
                );
        """
        self.cursor.execute(orders_q)

    def insert_sell_order(self, order, new_order, sell_amount, need_price):
        self.cursor.execute("""
            UPDATE orders
            SET
                order_type = 'sell',
                buy_finished = datetime(),
                sell_order_id = :sell_order_id,
                sell_created = datetime(),
                sell_amount = :sell_amount,
                sell_price = :sell_initial_price
            WHERE
                buy_order_id = :buy_order_id
        """,
            {
                'buy_order_id': order,
                'sell_order_id': new_order['orderId'],
                'sell_amount': sell_amount,
                'sell_initial_price': need_price
            }
        )
        self.conn.commit()

    def insert_buy_order(self, pair_name, new_order, my_amount, my_need_price):
        self.cursor.execute("""
            INSERT INTO orders(
                order_type,
                order_pair,
                buy_order_id,
                buy_amount,
                buy_price,
                buy_created
            )

            Values(
                'buy',
                :order_pair,
                :order_id,
                :buy_order_amount,
                :buy_initial_price,
                datetime()
            )
        """,
            {
                'order_pair': pair_name,
                'order_id': new_order['orderId'],
                'buy_order_amount': my_amount,
                'buy_initial_price': my_need_price
            }
        )
        self.conn.commit()

    def update_cancel_order(self, order):
        self.cursor.execute("""
            UPDATE orders
            SET
                buy_cancelled = datetime()
            WHERE
                buy_order_id = :buy_order_id
        """,
            {
                'buy_order_id': order
            }
        )

        self.conn.commit()

    def delete_sell_order(self, order):
        self.cursor.execute("""
            DELETE FROM orders
            WHERE
                sell_order_id = :sell_order_id
        """,
            {
                'sell_order_id': order
            }
        )
        self.conn.commit()

    def update_sell_order(self, order):
        self.cursor.execute("""
            UPDATE orders
            SET
                sell_finished = datetime()
            WHERE
                sell_order_id = :sell_order_id
        """,
            {
                'sell_order_id': order
            }
        )
        self.conn.commit()

    def select_unfilled_orders(self):
        orders_q = """
            SELECT
                CASE WHEN order_type='buy' THEN buy_order_id ELSE sell_order_id END order_id
                , order_type
                , order_pair
                , sell_amount
                , sell_price
                , strftime('%s',buy_created)
                , buy_amount
                , buy_price
            FROM
                orders
            WHERE
                buy_cancelled IS NULL AND CASE WHEN order_type='buy' THEN buy_finished IS NULL ELSE sell_finished IS NULL END
        """
        orders_info = {}

        for row in self.cursor.execute(orders_q):
            orders_info[str(row[0])] = {
                'order_type': row[1], 'order_pair': row[2], 'sell_amount': row[3],
                'sell_price': row[4], 'buy_created': row[5], 'buy_amount': row[6], 'buy_price': row[7]
            }
        return orders_info

    def select_filled_pairs(self, all_pairs):
        orders_q = """
            SELECT
                distinct(order_pair) pair
            FROM
                orders
            WHERE
                buy_cancelled IS NULL AND CASE WHEN order_type='buy' THEN buy_finished IS NULL ELSE sell_finished IS NULL END
        """
        # Получаем из базы все ордера, по которым есть торги, и исключаем их из списка, по которому будем создавать новые ордера
        for row in self.cursor.execute(orders_q):
            del all_pairs[row[0]]
        return all_pairs

    def close_conn(self):
        self.conn.close()
