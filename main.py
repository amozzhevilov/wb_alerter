import requests
import json
import os
from datetime import datetime, timezone, timedelta
from time import sleep

import wb

# извлекаем токены из env
WB_TOKEN = os.getenv('WB_TOKEN')
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

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

    bot_token = TELEGRAM_BOT_TOKEN
    bot_chat_id = TELEGRAM_CHAT_ID
    send_text = 'https://api.telegram.org/bot' + bot_token + \
        '/sendMessage?chat_id=' + bot_chat_id + \
        '&parse_mode=Markdown&text=' + bot_message

    response = requests.get(send_text)

    return response.json()

def send_message(result):
    msg=f''

    for i in result:
        msg += 'Склад: {}, дата: {}, коэф. {}.\n'.format(i['warehouseName'], datetime.fromisoformat(i['date']).strftime('%Y-%m-%d'), i['coefficient'])

    telegram_bot_sendtext(msg)

def get_warehouse (result, warehouse, coefficients):
    
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
            datetime.fromisoformat(coefficient['date']) - datetime.now(timezone.utc) >= timedelta(days=warehouse['delay']) and \
            coefficient not in result:
                result.append(coefficient)

# преобразуем фильтр по складам в JSON
warehouses = json.loads(WAREHOUSES)

# пустой лист для сохранения предыдущего состояния между циклами
old_list = []

# инициализируем класс для работы с WB API
wb = wb.wb(WB_TOKEN)

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
                    
    newlist = sorted(result, key=lambda d: d['warehouseName'])

    # оставляем склады, которые добавились на новой итерации 
    result = []
    for i in newlist:
        if i not in old_list:
            result.append(i)

    # отправляем сообщение пользователю
    send_message(result)

    # запоминаем состояние для следующего цикла
    old_list = newlist

    # спим
    sleep(60)
