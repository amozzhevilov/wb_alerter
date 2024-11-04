'''Send message to telegram about the availability of free warehouses on WB'''

import os
import sys
from datetime import datetime, timezone, timedelta
from time import sleep

import requests
import yaml
from wb import WB, MyError

# извлекаем токены из env
WB_TOKEN = os.getenv('WB_TOKEN')
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')
CONFIG_FILE = 'config.yaml'

# инициализируем класс для работы с WB API
wb = WB(WB_TOKEN)

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
        if coefficient['boxTypeName'] not in warehouse['boxTypeName']:
            continue

        # проверяем, подходит ли нам склад. * - подходит любой склад
        if 'warehouse' in warehouse and \
            coefficient['warehouseName'] not in warehouse['warehouse']:
            continue

        # проверяем коэф. склада, дату приемки и не добавляли ли мы склад ранее.
        if coefficient['coefficient'] <= warehouse['max_coefficient'] and \
            get_timedelta_to_now(coefficient['date']) >= timedelta(days=warehouse['delay']) and \
            coefficient not in result:
            result.append(coefficient)

def main():
    '''Main function'''

    # Загружаем конфигурацию из CONFIG_FILE
    try:
    # Open file in read-only mode
        with open(CONFIG_FILE, 'r', encoding='utf-8') as file:
            warehouses = yaml.safe_load(file)
    except IOError as e:
        print("An error occurred:", e)
        sys.exit(e.errno)
    except yaml.YAMLError as e:
        print("An error occurred:", e)
        sys.exit(-1)

    # пустой лист для сохранения предыдущего состояния между циклами
    previous_list = []

    while True:
        try:
            # извлекаем коэффициенты по складам
            coefficients = wb.get_coefficients()
        except MyError:
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
