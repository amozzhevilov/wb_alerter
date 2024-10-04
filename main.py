'''Send message to telegram about the availability of free warehouses on WB'''

import json
import os
from datetime import datetime, timezone, timedelta
from time import sleep

import requests
import wb

# извлекаем токены из env
WB_TOKEN = os.getenv('WB_TOKEN')
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

# инициализируем класс для работы с WB API
wb = wb.WB(WB_TOKEN)

# фильтр по складам
WAREHOUSES = '''
[
    {
        "warehouse": "Екатеринбург - Испытателей 14г|Екатеринбург - Перспективный 12/2|СЦ Екатеринбург 2 (Альпинистов)",
        "delay": 0,
        "min_coefficient": 5,
        "boxTypeName": "Короба"
    } ,
    {
        "warehouse": "*",
        "delay": 7,
        "min_coefficient": 5,
        "boxTypeName": "Короба"
    }   
]
'''

def telegram_bot_sendtext(bot_message):
    '''Send message to telegram.'''
    bot_token = TELEGRAM_BOT_TOKEN
    bot_chat_id = TELEGRAM_CHAT_ID
    send_text = 'https://api.telegram.org/bot' + bot_token + \
        '/sendMessage?chat_id=' + bot_chat_id + \
        '&parse_mode=Markdown&text=' + bot_message

    response = requests.get(send_text, timeout=10)

    return response.json()

def send_message(result):
    '''Convert relust list to user message'''
    msg=""

    for i in result:
        msg += f"Склад: {i['warehouseName']}, "
        msg += f"дата: {datetime.fromisoformat(i['date']).strftime('%Y-%m-%d')}, "
        msg += f"коэф. {i['coefficient']}.\n"
    telegram_bot_sendtext(msg)

def get_timedelta_to_now(date):
    '''Return timedelta from date to now'''
    return datetime.fromisoformat(date) - datetime.now(timezone.utc)

def get_warehouse (result, warehouse, coefficients):
    '''Find warehouse by condition'''
    for coefficient in coefficients:

        # коэф -1 - склад не работает
        if coefficient['coefficient'] == -1:
            continue

        # проверяем, подходит ли нам тип упаковки
        if coefficient['boxTypeName'] not in warehouse['boxTypeName'].split('|'):
            continue

        # проверяем, подходит ли нам склад. * - подходит любой склад
        if warehouse['warehouse'] != "*" and \
            coefficient['warehouseName'] not in warehouse['warehouse'].split('|'):
            continue

        # проверяем коэф. склада, дату приемки и не добавляли ли мы склад ранее.
        if coefficient['coefficient'] <= warehouse['min_coefficient'] and \
            get_timedelta_to_now(coefficient['date']) >= timedelta(days=warehouse['delay']) and \
            coefficient not in result:
            result.append(coefficient)

def main():
    '''Main function'''
    # преобразуем фильтр по складам в JSON
    warehouses = json.loads(WAREHOUSES)

    # пустой лист для сохранения предыдущего состояния между циклами
    previous_list = []

    while True:
        # извлекаем коэффициенты по складам
        x = wb.get_coefficients()

        # если извлечение завершилось ошибкой, ждём 10 секунд и запускаем цикл по новой
        if x != -1:
            coefficients = json.loads(x.text)
        else:
            sleep(10)
            continue

        # в лист result будем добавлять склады, которые нам подходят
        result = []
        for warehouse in warehouses:
            get_warehouse(result, warehouse, coefficients)

        current_list = sorted(result, key=lambda d: d['warehouseName'])

        # оставляем склады, которые добавились на новой итерации
        result = []
        for i in current_list:
            if i not in previous_list:
                result.append(i)

        # отправляем сообщение пользователю
        send_message(result)

        # запоминаем состояние для следующего цикла
        previous_list = current_list

        # спим
        sleep(60)

if __name__ == "__main__":
    main()
