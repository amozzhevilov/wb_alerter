"""Send message to telegram about the availability of free warehouses on WB"""

import os
import asyncio
from fuzzywuzzy import process
from telebot import async_telebot, asyncio_filters, types
from telebot.asyncio_storage import StateMemoryStorage
from telebot.states import State, StatesGroup
from telebot.states.asyncio.context import StateContext
from telebot.states.asyncio.middleware import StateMiddleware
from telebot.types import ReplyParameters
from time import sleep

from db import DB
from wb import WB, MyError

# минимальный коээфициент для выбора названия склада
MIN_SCORE_WAREHOUSE = 70

# извлекаем токены из env
WB_TOKEN = os.getenv('WB_TOKEN')
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

# инициализируем класс для работы с WB API
wb = WB(WB_TOKEN)

# инициализируем класс для работы с DB
db = DB(DB_HOST='172.18.2.143')

# инициализируем модуль Telebot
state_storage = StateMemoryStorage()
bot = async_telebot.AsyncTeleBot(TELEGRAM_BOT_TOKEN, state_storage=state_storage)


class AddWarehouseStates(StatesGroup):
    name = State()
    id = State()
    max_coef = State()
    delay = State()
    accept_type = State()


class DelWarehouseStates(StatesGroup):
    name = State()


ACCEPT_TYPES = [
    'Суперсейф',
    'Монопаллеты',
    'Короба',
    'QR-поставка с коробами',
]


@bot.message_handler(commands=['start'])
async def start(message):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    btn1 = types.KeyboardButton('👋 Поздороваться')
    markup.add(btn1)
    await bot.send_message(
        message.from_user.id,
        f'👋 Привет {str(message.chat.first_name)}! Я твой бот-помошник!',
        reply_parameters=ReplyParameters(message_id=message.message_id),
        reply_markup=markup,
    )


@bot.message_handler(
    text=[
        "👋 Поздороваться",
        "📦 Посмотреть активные склады",
        "📦 Посмотреть все доступные склады",
        "📦 Посмотреть все доступные СЦ",
        "➕ Добавить склад/СЦ",
        "❌ Удалить склад/СЦ",
    ]
)
async def get_text_message(message: types.Message, state: StateContext):
    if message.text == '👋 Поздороваться':
        db.update_user(message.chat.id, message.chat.first_name)
        await bot.send_message(
            message.from_user.id,
            '❓ Задайте интересующий вопрос',
            reply_markup=get_default_menu(),
        )

    elif message.text == '📦 Посмотреть активные склады':
        user_id = int(message.chat.id)
        warehouses_list = db.read_orders(user_id)
        msg = get_orders_from_list(warehouses_list)
        if not msg:
            msg = 'Вы не отслеживайте ни один склад!'
        await bot.send_message(message.from_user.id, msg, reply_markup=get_default_menu())

    elif message.text == '📦 Посмотреть все доступные склады':
        # warehouses_list = db.read_warehouses('^(?!СЦ)')
        warehouses_list = db.read_accessible_warehouses('^(?!СЦ)')
        msg = get_msg_from_list(warehouses_list)
        await bot.send_message(message.from_user.id, msg, reply_markup=get_default_menu())

    elif message.text == '📦 Посмотреть все доступные СЦ':
        # warehouses_list = db.read_warehouses('^(СЦ)')
        warehouses_list = db.read_accessible_warehouses('^(СЦ)')
        msg = get_msg_from_list(warehouses_list)
        await bot.send_message(message.from_user.id, msg, reply_markup=get_default_menu())

    elif message.text == '➕ Добавить склад/СЦ':
        await state.set(AddWarehouseStates.name)
        await bot.send_message(
            message.chat.id,
            '📦 Введите название склада/СЦ',
            reply_parameters=ReplyParameters(message_id=message.message_id),
        )

    elif message.text == '❌ Удалить склад/СЦ':
        if not db.read_orders(message.chat.id):
            msg = 'Вы не отслеживайте ни один склад!'
            await bot.send_message(message.from_user.id, msg, reply_markup=get_default_menu())
            return
        await state.set(DelWarehouseStates.name)
        await bot.send_message(
            message.chat.id,
            '📦 Введите название склада/СЦ',
            reply_parameters=ReplyParameters(message_id=message.message_id),
        )


@bot.message_handler(state=AddWarehouseStates.name)
async def warehouse_name_get(message: types.Message, state: StateContext):
    try:
        warehouses_list = db.read_warehouses()
        warehouse, score = process.extractOne(message.text, warehouses_list)
        if score < MIN_SCORE_WAREHOUSE:
            await state.set(AddWarehouseStates.name)
            await bot.send_message(
                message.chat.id,
                'Не могу распознать название склада. Введите название без ошибок.',
                reply_parameters=ReplyParameters(message_id=message.message_id),
            )
            return
        await state.add_data(name=warehouse)
        await state.add_data(id=db.read_warehouse_id(warehouse))

        await state.set(AddWarehouseStates.max_coef)
        await bot.send_message(
            message.chat.id,
            'Укажите максимальный коэфициент приёмки от 0 до 20.',
            reply_parameters=ReplyParameters(message_id=message.message_id),
        )
    except Exception as error:
        await bot.reply_to(message, f'oooops: {error}')


@bot.message_handler(state=AddWarehouseStates.max_coef)
async def warehouse_coef_get(message: types.Message, state: StateContext):
    try:
        try:
            max_coef = int(message.text)
        except:
            await bot.send_message(
                message.chat.id,
                'В ответе должно быть число. Укажите максимальный коэфициент приёмки от 0 до 20.',
                reply_parameters=ReplyParameters(message_id=message.message_id),
            )
            return
        if max_coef < 0 or max_coef > 20:
            await bot.send_message(
                message.chat.id,
                'Укажите максимальный коэфициент приёмки от 0 до 20.',
                reply_parameters=ReplyParameters(message_id=message.message_id),
            )
            return
        await state.add_data(max_coef=max_coef)
        await state.set(AddWarehouseStates.delay)
        await bot.send_message(
            message.chat.id,
            'Через сколько дней от текущей даты начинаем искать слоты?',
            reply_parameters=ReplyParameters(message_id=message.message_id),
        )
    except Exception as error:
        await bot.reply_to(message, f'oooops: {error}')


@bot.message_handler(state=AddWarehouseStates.delay)
async def warehouse_delay_get(message: types.Message, state: StateContext):
    try:
        try:
            delay = int(message.text)
        except:
            await bot.send_message(
                message.chat.id,
                'В ответе должно быть число. Через сколько дней от текущей даты начинаем искать слоты?',
                reply_parameters=ReplyParameters(message_id=message.message_id),
            )
            return
        await state.add_data(delay=delay)
        await state.set(AddWarehouseStates.accept_type)

        keyboard = types.ReplyKeyboardMarkup(row_width=1)
        buttons = [types.KeyboardButton(accept_type) for accept_type in ACCEPT_TYPES]
        keyboard.add(*buttons)

        await bot.send_message(
            message.chat.id,
            'Выберите тип поставки:',
            reply_markup=keyboard,
            reply_parameters=ReplyParameters(message_id=message.message_id),
        )

    except Exception as error:
        await bot.reply_to(message, f'oooops: {error}')


@bot.message_handler(state=AddWarehouseStates.accept_type)
async def warehouse_accept_type_get(message: types.Message, state: StateContext):
    try:
        if message.text not in ACCEPT_TYPES:
            keyboard = types.ReplyKeyboardMarkup(row_width=1)
            buttons = [types.KeyboardButton(accept_type) for accept_type in ACCEPT_TYPES]
            keyboard.add(*buttons)

            await bot.send_message(
                message.chat.id,
                'Выберите тип поставки:',
                reply_markup=keyboard,
                reply_parameters=ReplyParameters(message_id=message.message_id),
            )
        await state.add_data(accept_type=message.text)
        async with state.data() as data:
            name = data.get('name')
            id = data.get('id')
            max_coef = data.get('max_coef')
            delay = data.get('delay')
            accept_type = data.get('accept_type')
            db.create_order(message.chat.id, id, max_coef, delay, accept_type)
            msg = (
                f'Создана заявка на отслеживание: склад - {name}, '
                f'максимальный коэф приемки - {max_coef}, '
                f'смотрим слоты через {delay} дней, '
                f'тип поставки - {accept_type}. '
            )
        await bot.send_message(
            message.chat.id,
            msg,
            reply_markup=get_default_menu(),
            reply_parameters=ReplyParameters(message_id=message.message_id),
        )
        await state.delete()
    except Exception as error:
        await bot.reply_to(message, f'oooops: {error}')


DelWarehouseStates


@bot.message_handler(state=DelWarehouseStates.name)
async def warehouse_delete(message: types.Message, state: StateContext):
    try:
        warehouses_list = db.read_warehouses()
        warehouse, score = process.extractOne(message.text, warehouses_list)
        if score < MIN_SCORE_WAREHOUSE:
            await state.set(DelWarehouseStates.name)
            await bot.send_message(
                message.chat.id,
                'Не могу распознать название склада. Введите название без ошибок.',
                reply_parameters=ReplyParameters(message_id=message.message_id),
            )
            return
        warehouse_id = db.read_warehouse_id(warehouse)
        db.delete_order(message.chat.id, warehouse_id)
        await bot.send_message(
            message.chat.id,
            f'Cклад {warehouse} удалён из отслеживания!',
            reply_markup=get_default_menu(),
        )
    except Exception as error:
        await bot.reply_to(message, f'oooops: {error}')


def get_default_menu():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=1)
    btn1 = types.KeyboardButton('📦 Посмотреть активные склады')
    btn2 = types.KeyboardButton('📦 Посмотреть все доступные склады')
    btn3 = types.KeyboardButton('📦 Посмотреть все доступные СЦ')
    btn4 = types.KeyboardButton('➕ Добавить склад/СЦ')
    btn5 = types.KeyboardButton('❌ Удалить склад/СЦ')
    markup.add(btn1, btn2, btn3, btn4, btn5)
    return markup


async def send_message_to_user(messages):
    for key in list(messages.keys()):
        chat_id = key
        text = messages.get(key)
        await bot.send_message(chat_id, text)


def get_msg_from_list(list, prefix='', postfix=''):
    msg = ''
    for row in list:
        accept_type, warehouses, min_coef, max_coef = row
        msg += f'{prefix} 📦: {accept_type}, 🚛: {warehouses}, ₽: {min_coef}-{max_coef} {postfix}\n'
    return msg


def get_orders_from_list(orders):
    msg = ''
    for order in orders:
        warehouse, max_coef, delay, type = order
        msg += f'Склад: {warehouse}, '
        msg += f'макс. коэф. приемки {max_coef}, '
        msg += f'смотрим слоты через {delay} дн., '
        msg += f'тип поставки - {type}\n'
    return msg


def get_msg_from_result(slots):
    result = {}
    for slot in slots:
        user_id, warehose_name, acceptance_date, acceptance_coef, acceptance_type = slot
        msg = ''
        if user_id in result:
            msg = result[user_id]
        msg += f'Склад: {warehose_name}, '
        msg += f'дата приемки: {acceptance_date.strftime("%d.%m.%Y")}, '
        msg += f'коэф. приемки: {acceptance_coef}, '
        msg += f'тип поставки: {acceptance_type}.\n'
        result[user_id] = msg
    return result


async def main():
    bot.add_custom_filter(asyncio_filters.StateFilter(bot))
    bot.add_custom_filter(asyncio_filters.TextMatchFilter())
    bot.setup_middleware(StateMiddleware(bot))
    asyncio.create_task(bot.polling())

    # пустой лист для сохранения предыдущего состояния между циклами
    previous_result = []

    while True:
        try:
            pass
            # извлекаем коэффициенты по складам
            coefficients = wb.get_coefficients()
        except MyError:
            print('Ooppsss... we get error')
            sleep(10)
            continue

        db.update_limits(coefficients)

        current_result = db.read_all_slots()

        result = [val for val in current_result if val not in previous_result]
        previous_result = current_result

        msg = get_msg_from_result(result)

        # отправляем сообщение пользователям
        task_send_message = asyncio.create_task(send_message_to_user(msg))
        await task_send_message

        # спим
        await asyncio.sleep(15)


if __name__ == '__main__':
    asyncio.run(main())
