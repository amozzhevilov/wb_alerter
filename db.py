import logging
import psycopg2


class DB:
    """Class for work with POSTGRE"""

    def __init__(
        self,
        DB_NAME='postgres',
        DB_USER='postgres',
        DB_PASSWORD='postgres',
        DB_HOST='postgres',
        DB_PORT=5432,
    ) -> None:
        self.DATABASE_URL = f'postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}'

    def __connect(self):
        """Функция подключения к базе данных"""
        connect = psycopg2.connect(self.DATABASE_URL)
        return connect

    def update_user(self, user_id: int, name: str):
        try:
            with self.__connect() as conn, conn.cursor() as cur:
                query = """
                INSERT INTO users (id, name)
                VALUES (%s, %s)
                ON CONFLICT (id) DO UPDATE
                SET name = excluded.name;
                """
                cur.execute(
                    query,
                    (
                        user_id,  # ID пользователя
                        name,  # Имя пользователя
                    ),
                )
                conn.commit()
        except psycopg2.Error as error:
            logging.warning(f'Error update user {user_id}, {name}: {error}')

    def read_warehouses(self, regexp='.*'):
        try:
            with self.__connect() as conn, conn.cursor() as cur:
                query = """
                SELECT
                    name
                FROM
                    warehouses
                WHERE
                    name ~ %s;
                """
                cur.execute(query, (regexp,))
                rows = cur.fetchall()
        except psycopg2.Error as error:
            logging.warning(f'Error read warehouse, regexp {regexp}: {error}')

        result = []
        for row in rows:
            for element in row:
                result.append(element)
        return result

    def create_warehouses(self, warehouses):
        try:
            with self.__connect() as conn, conn.cursor() as cur:
                query = 'DELETE FROM limits;'
                cur.execute(query)
                query = """
                INSERT INTO warehouses (id, name)
                VALUES (%s, %s)
                ON CONFLICT (id) DO UPDATE
                SET name = excluded.name;
                """
                for warehouse in warehouses:
                    cur.execute(
                        query,
                        (
                            warehouse['ID'],  # ID склада
                            warehouse['name'],  # Наименование склада
                        ),
                    )
                conn.commit()
        except psycopg2.Error as error:
            logging.warning(f'Error update warehouses: {error}')

    def read_accessible_warehouses(self, regexp='.*'):
        try:
            with self.__connect() as conn, conn.cursor() as cur:
                query = """
                SELECT
                    limits.type,
                    warehouses.name,
                    min(limits.coef),
                    max(limits.coef)
                FROM
                    limits
                JOIN
                    warehouses
                ON
                    warehouses.id = limits.warehouse_id
                WHERE
                    limits.coef <> -1
                    AND warehouses.name ~ %s
                GROUP BY
                    limits.type,warehouses.id
                ORDER BY
                    limits.type, warehouses.name;
                """
                cur.execute(query, (regexp,))
                result = cur.fetchall()
        except psycopg2.Error as error:
            logging.warning(f'Error read accessible warehouse, regexp {regexp}: {error}')

        return result

    def read_warehouse_id(self, warehouse: str):
        try:
            with self.__connect() as conn, conn.cursor() as cur:
                query = """
                SELECT
                    id
                FROM
                    warehouses
                WHERE
                    name = %s;
                """
                cur.execute(query, (warehouse,))
                rows = cur.fetchone()
        except psycopg2.Error as error:
            logging.warning(f'Error read warehouse id, warehouse {warehouse}: {error}')

        if rows is None:
            # User does not exist
            return -1
        return rows[0]

    def create_order(self, user_id: int, warehouse_id: int, max_coef: int, delay: int, accept_type: str):
        try:
            with self.__connect() as conn, conn.cursor() as cur:
                query = """
                INSERT INTO orders (user_id, warehouse_id, max_coef, delay, type)
                VALUES (%s, %s, %s, %s, %s)
                """
                cur.execute(
                    query,
                    (
                        user_id,  # ID пользователя
                        warehouse_id,  # ID склада
                        max_coef,  # Макс коэф приемки
                        delay,  # Через сколько дней ищем слоты
                        accept_type,  # тип поставки
                    ),
                )
                conn.commit()
        except psycopg2.Error as error:
            logging.warning(f'Error create order: {error}')

    def delete_order(self, user_id: int, warehouse_id: int):
        try:
            with self.__connect() as conn, conn.cursor() as cur:
                query = """
                DELETE FROM
                    orders
                WHERE
                    user_id = %s AND
                    warehouse_id = %s
                """
                cur.execute(
                    query,
                    (
                        user_id,  # ID пользователя
                        warehouse_id,  # ID склада
                    ),
                )
                conn.commit()
        except psycopg2.Error as error:
            logging.warning(f'Error delete order. User_id {user_id}, warehouse {warehouse_id}: {error}')

    def read_orders(self, user_id: int):
        result = []
        try:
            with self.__connect() as conn, conn.cursor() as cur:
                query = """
                SELECT
                    warehouses.name,
                    orders.max_coef,
                    orders.delay,
                    orders.type
                FROM
                    orders
                JOIN
                    warehouses
                ON
                    warehouses.id = orders.warehouse_id
                WHERE
                    user_id = %s;
                """
                cur.execute(query, (user_id,))
                result = cur.fetchall()
        except psycopg2.Error as error:
            logging.warning(f'Error read orders for user_id {user_id}: {error}')

        return result

    def update_limits(self, coefficients):
        try:
            with self.__connect() as conn, conn.cursor() as cur:
                query = 'DELETE FROM limits;'
                cur.execute(query)
                query = """
                INSERT INTO limits (warehouse_id, date, coef, type)
                VALUES (%s, %s, %s, %s)
                """
                for coefficient in coefficients:
                    cur.execute(
                        query,
                        (
                            coefficient['warehouseID'],  # ID склада
                            coefficient['date'],  # Дата поставки
                            coefficient['coefficient'],  # Коэффициент приемки
                            coefficient['boxTypeName'],  # Тип поставки
                        ),
                    )
                conn.commit()
        except psycopg2.Error as error:
            logging.warning(f'Error update limits: {error}')

        pass

    def read_all_slots(self):
        result = []
        try:
            with self.__connect() as conn, conn.cursor() as cur:
                query = """
                SELECT
                    orders.user_id,
                    warehouses.name,
                    limits.date,
                    limits.coef,
                    limits.type
                FROM
                    orders
                JOIN
                    limits
                ON
                    orders.warehouse_id = limits.warehouse_id
                JOIN
                    warehouses
                ON
                    warehouses.id = limits.warehouse_id
                WHERE
                    limits.coef <= orders.max_coef
                    AND limits.coef <> -1
                    AND limits.type = orders.type
                    AND limits.date > CURRENT_DATE + orders.delay
                ORDER BY orders.user_id, warehouses.name, limits.date;
                """
                cur.execute(query)
                result = cur.fetchall()
        except psycopg2.Error as error:
            logging.warning(f'Error read all slots: {error}')

        return result

    def find_slot(self, max_coef: int, delay: int, accept_type: str) -> tuple:
        result = []
        try:
            with self.__connect() as conn, conn.cursor() as cur:
                query = """
                SELECT
                    warehouses.name,
                    limits.date,
                    limits.coef
                FROM
                    limits
                JOIN
                    warehouses
                ON
                    warehouses.id = limits.warehouse_id
                WHERE
                    limits.type = %s
                    AND limits.coef <> -1
                    AND limits.coef < %s
                    AND limits.date > CURRENT_DATE + %s
                ORDER BY warehouses.name, limits.date;
                """
                cur.execute(
                    query,
                    (
                        accept_type,
                        max_coef,
                        delay,
                    ),
                )
                result = cur.fetchall()
        except psycopg2.Error as error:
            logging.warning(f'Error find slots: {error}')

        return result


def main():
    pass


if __name__ == '__main__':
    main()
