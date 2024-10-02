import requests, json, os
from datetime import datetime, timezone, timedelta
from time import sleep

WB_TOKEN=os.getenv('WB_TOKEN')
TELEGRAM_BOT_TOKEN=os.getenv('TELEGRAM_BOT_TOKEN')
TELEGRAM_CHAT_ID=os.getenv('TELEGRAM_CHAT_ID')

def telegram_bot_sendtext(bot_message):

   bot_token = TELEGRAM_BOT_TOKEN
   bot_chatID = TELEGRAM_CHAT_ID
   send_text = 'https://api.telegram.org/bot' + bot_token + '/sendMessage?chat_id=' + bot_chatID + '&parse_mode=Markdown&text=' + bot_message

   response = requests.get(send_text)

   return response.json()


warehouses_input = '''
[
    {
        "warehouse": "Коледино",
        "delay": 5,
        "min_coefficient": 3
    },
    {
        "warehouse": "Казань",
        "delay": 7,
        "min_coefficient": 3
    }    
]
'''

old_list = []

while True:

    url = 'https://supplies-api.wildberries.ru/api/v1/acceptance/coefficients'
    headers = {'Authorization':WB_TOKEN}
    x = requests.get(url, headers=headers)

    warehouses = json.loads(warehouses_input)
    coefficients = json.loads(x.text)

    result = []

    for warehouse in warehouses:

        for coefficient in coefficients: 
            
            if coefficient['boxTypeName'] != 'Короба':
                continue

            if coefficient['coefficient'] == -1:
                continue        

            # if coefficient['warehouseName'] == warehouse['warehouse'] and \
            #     coefficient['coefficient'] <= warehouse['min_coefficient'] and \
            #     datetime.fromisoformat(coefficient['date']) - datetime.now(timezone.utc) < timedelta(days=warehouse['delay']):
            #         print(coefficient)

            if coefficient['coefficient'] <= 5 and \
                datetime.fromisoformat(coefficient['date']) - datetime.now(timezone.utc) >= timedelta(days=7) and \
                coefficient not in result:
                    result.append(coefficient)
                    
    newlist = sorted(result, key=lambda d: d['warehouseName'])

    result = []

    for i in newlist:
        if i not in old_list:
            result.append(i)

    msg=''

    for i in result:
        msg += 'Склад: {}, дата: {}, коэф. {}.\n'.format(i['warehouseName'], datetime.fromisoformat(i['date']).strftime('%Y-%m-%d'), i['coefficient'])

    telegram_bot_sendtext(msg)

    old_list = newlist

    sleep(60)