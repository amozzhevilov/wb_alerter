"""Send message to telegram about the availability of free warehouses on WB"""

import os
import re
import requests
import sys
import yaml
from datetime import datetime, timedelta, timezone
from time import sleep
from telebot import telebot, types

from wb import WB, MyError

# извлекаем токены из env
WB_TOKEN = os.getenv('WB_TOKEN')
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')
CONFIG_FILE = 'config.yaml'

# инициализируем класс для работы с WB API
wb = WB(WB_TOKEN)

# инициализируем модуль Telebot
telegram_bot = telebot.TeleBot(TELEGRAM_BOT_TOKEN)


@telegram_bot.message_handler(commands=['start'])
def start(message):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    btn1 = types.KeyboardButton('👋 Поздороваться')
    # btn2 = types.KeyboardButton('🇬🇧 English')
    markup.add(btn1)
    telegram_bot.send_message(message.from_user.id, f'👋 Привет {str(message.chat.first_name)}! Я твой бот-помошник!', reply_markup=markup)    

@telegram_bot.message_handler(commands=['add'])
def add(message):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    telegram_bot.send_message(message.from_user.id, f'✅ Склад добавлен!', reply_markup=markup)    


@telegram_bot.message_handler(content_types=['text'])
def get_text_message(message):
    if message.text == '👋 Поздороваться':
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=1)
        btn1 = types.KeyboardButton('📦 Посмотреть активные склады')
        btn2 = types.KeyboardButton('📦 Посмотреть все доступные склады')
        btn3 = types.KeyboardButton('📦 Посмотреть все доступные СЦ')
        btn4 = types.KeyboardButton('➕ Добавить склад/СЦ')
        btn5 = types.KeyboardButton('❌ Удалить склад/СЦ')
        markup.add(btn1, btn2, btn3, btn4, btn5)
        telegram_bot.send_message(message.from_user.id, '❓ Задайте интересующий вопрос', reply_markup=markup)  #ответ бота
    elif message.text == '📦 Посмотреть активные склады':
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
        user_id = int(message.chat.id)
        warehouses_list = get_warehouses_for_user_id(warehouses, user_id)
        msg = get_msg_from_list(warehouses_list)
        telegram_bot.send_message(message.from_user.id, msg, reply_markup=markup)
    elif message.text == '📦 Посмотреть все доступные склады':
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
        warehouses_list = get_warehouses_by_name(wb.get_warehouses(), 'name', '^(?!СЦ)')
        msg = get_msg_from_list(warehouses_list, '📦')
        telegram_bot.send_message(message.from_user.id, msg, reply_markup=markup)
    elif message.text == '📦 Посмотреть все доступные СЦ':
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
        warehouses_list = get_warehouses_by_name(wb.get_warehouses(), 'name', '^(СЦ)')
        msg = get_msg_from_list(warehouses_list, '🚛')
        telegram_bot.send_message(message.from_user.id, msg, reply_markup=markup)
    elif message.text == '➕ Добавить склад/СЦ':
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
        telegram_bot.send_message(message.from_user.id, 'ℹ️ Введите команду /add <название склада> <максимальный коэф. приемки> <задержку в днях>', reply_markup=markup)


def telegram_bot_sendtext(bot_message):
    """Send message to telegram."""
    bot_token = TELEGRAM_BOT_TOKEN
    bot_chat_id = TELEGRAM_CHAT_ID
    send_text = (
        'https://api.telegram.org/bot'
        + bot_token
        + '/sendMessage?chat_id='
        + bot_chat_id
        + '&parse_mode=Markdown&text='
        + bot_message
    )

    response = requests.get(send_text, timeout=10)

    return response.json()


def send_message(result):
    """Convert relust list to user message"""
    msg = ''

    for i in result:
        msg += f"Склад: {i['warehouseName']}, "
        msg += f"дата: {datetime.fromisoformat(i['date']).strftime('%Y-%m-%d')}, "
        msg += f"коэф. {i['coefficient']}.\n"
    # telegram_bot_sendtext(msg)


def get_timedelta_to_now(date):
    """Return timedelta from date to now"""
    return datetime.fromisoformat(date) - datetime.now(timezone.utc)


def get_warehouses_for_user_id(warehouses, user_id):
    """Get lits of warehouses for user_id"""
    result = []
    for warehouse in warehouses:
        if warehouse['user_id'] == user_id:
            for wh in warehouse['warehouse']:
                result.append(wh)
    return result


def get_warehouses_by_name(warehouses, field, regexp='.*'):
    result = []
    for warehouse in warehouses:
        if (
            field in warehouse
            and re.match(regexp, warehouse[field])
        ):
            result.append(warehouse[field])
    return result


def get_msg_from_list(list, prefix='', postfix=''):
    msg = ''
    for element in list:
        msg += f'{prefix} {element} {postfix}\n'
    return msg


def get_warehouse(result, warehouse, coefficients):
    """Find warehouse by condition"""

    for coefficient in coefficients:

        # коэф -1 - склад не работает
        if coefficient['coefficient'] == -1:
            continue

        # проверяем, подходит ли нам тип упаковки
        if coefficient['boxTypeName'] not in warehouse['boxTypeName']:
            continue

        # проверяем, подходит ли нам склад. * - подходит любой склад
        if 'warehouse' in warehouse and coefficient['warehouseName'] not in warehouse['warehouse']:
            continue

        # проверяем коэф. склада, дату приемки и не добавляли ли мы склад ранее.
        if (
            coefficient['coefficient'] <= warehouse['max_coefficient']
            and get_timedelta_to_now(coefficient['date']) >= timedelta(days=warehouse['delay'])
            and coefficient not in result
        ):
            result.append(coefficient)


def main():
    """Main function"""
    global warehouses
    # Загружаем конфигурацию из CONFIG_FILE
    try:
        # Open file in read-only mode
        with open(CONFIG_FILE, 'r', encoding='utf-8') as file:
            warehouses = yaml.safe_load(file)
    except IOError as e:
        sys.exit(e.errno)
    except yaml.YAMLError as error:
        print(f'Error yaml parsing: {error}')
        sys.exit(-1)

    telegram_bot.polling(none_stop=True, interval=0) #обязательная для работы бота часть

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


if __name__ == '__main__':
    main()
