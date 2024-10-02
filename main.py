import requests, json, os
from datetime import datetime, timezone, timedelta
from time import sleep

import wb

WB_TOKEN=os.getenv('WB_TOKEN')
TELEGRAM_BOT_TOKEN=os.getenv('TELEGRAM_BOT_TOKEN')
TELEGRAM_CHAT_ID=os.getenv('TELEGRAM_CHAT_ID')

def telegram_bot_sendtext(bot_message):

   bot_token = TELEGRAM_BOT_TOKEN
   bot_chatID = TELEGRAM_CHAT_ID
   send_text = 'https://api.telegram.org/bot' + bot_token + '/sendMessage?chat_id=' + bot_chatID + '&parse_mode=Markdown&text=' + bot_message

   response = requests.get(send_text)

   return response.json()

def get_warehouse (result, warehouse, coefficients):
    
    for coefficient in coefficients: 
        
        if coefficient['coefficient'] == -1:
            continue

        if coefficient['boxTypeName'] not in warehouse['boxTypeName'].split('|'):
            continue

        if warehouse['warehouse'] != "*" and \
            coefficient['warehouseName'] not in warehouse['warehouse'].split('|'):
            continue

        if coefficient['coefficient'] <= warehouse['min_coefficient'] and \
            datetime.fromisoformat(coefficient['date']) - datetime.now(timezone.utc) >= timedelta(days=warehouse['delay']) and \
            coefficient not in result:
                result.append(coefficient)

warehouses = '''
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
warehouses = json.loads(warehouses)

old_list = []

wb = wb.wb(WB_TOKEN)

while True:

    x = wb.get_coefficients()

    if x != -1:
        coefficients = json.loads(x.text)
    else:
        sleep(10)
        continue

    result = []

    for warehouse in warehouses:
        get_warehouse(result, warehouse, coefficients)
                    
    newlist = sorted(result, key=lambda d: d['warehouseName'])

    result = []

    for i in newlist:
        if i not in old_list:
            result.append(i)

    msg=''

    for i in result:
        msg += 'Склад: {}, дата: {}, коэф. {}.\n'.format(i['warehouseName'], datetime.fromisoformat(i['date']).strftime('%Y-%m-%d'), i['coefficient'])

    # print(msg)
    # exit(0)

    telegram_bot_sendtext(msg)

    old_list = newlist

    sleep(60)