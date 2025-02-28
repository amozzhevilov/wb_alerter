"""Send message to telegram about the availability of free warehouses on WB"""

import asyncio
import logging
import os
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

# инициализируем класс для работы с WB API
wb = WB(WB_TOKEN)

# инициализируем класс для работы с DB
db = DB()

# инициализируем модуль Telebot
state_storage = StateMemoryStorage()
bot = async_telebot.AsyncTeleBot(TELEGRAM_BOT_TOKEN, state_storage=state_storage)


class AddWarehouseStates(StatesGroup):
    name = State()
    warehouse_id = State()
    max_coef = State()
    delay = State()
    accept_type = State()


class DelWarehouseStates(StatesGroup):
    name = State()


class FindSlot(StatesGroup):
    max_coef = State()
    delay = State()
    accept_type = State()


ACCEPT_TYPES = [
    'Суперсейф',
    'Монопаллеты',
    'Короба',
    'QR-поставка с коробами',
]

MENU_BUTTONS = {
    '⏪️ Назад': (
        '📦 Мои склады',
        '🍒 Склады WB',
        '🔍 Найти слот',
    ),
    '📦 Мои склады': (
        '🔍 Показать все',
        '➕ Добавить склад/СЦ',
        '❌ Удалить склад/СЦ',
        '⏪️ Назад',
    ),
    '🍒 Склады WB': (
        '🔍 Показать все склады',
        '🔍 Показать все СЦ',
        '🔍 Показать доступные склады',
        '🔍 Показать доступные СЦ',
        '⏪️ Назад',
    ),
}


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
        '👋 Поздороваться',
    ],
)
async def get_text_message(message: types.Message, state: StateContext):
    db.update_user(message.chat.id, message.chat.first_name)
    await bot.send_message(
        message.from_user.id,
        '❓ Задайте интересующий вопрос',
        reply_markup=get_menu_buttons(),
    )


@bot.message_handler(
    text=[
        '📦 Мои склады',
        '🍒 Склады WB',
        '⏪️ Назад',
    ],
)
async def get_menu(message: types.Message, state: StateContext):
    await bot.send_message(
        message.from_user.id,
        '❓ Задайте интересующий вопрос',
        reply_markup=get_menu_buttons(message.text),
    )


def get_menu_buttons(menu='⏪️ Назад') -> types.ReplyKeyboardMarkup:
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=1)
    buttons = [types.KeyboardButton(button) for button in MENU_BUTTONS[menu]]
    keyboard.add(*buttons)
    return keyboard


@bot.message_handler(
    text=[
        '🔍 Показать все',
    ],
)
async def look_my_warehouse(message: types.Message, state: StateContext):
    user_id = int(message.chat.id)
    warehouses_list = db.read_orders(user_id)
    msg = get_orders_from_list(warehouses_list)
    if not msg:
        msg = 'Вы не отслеживайте ни один склад!'
    await bot.send_message(message.from_user.id, msg, reply_markup=get_menu_buttons('📦 Мои склады'))


@bot.message_handler(
    text=[
        '➕ Добавить склад/СЦ',
    ],
)
async def add_my_warehouse(message: types.Message, state: StateContext):
    await state.set(AddWarehouseStates.name)
    await bot.send_message(
        message.chat.id,
        '📦 Введите название склада/СЦ',
        reply_parameters=ReplyParameters(message_id=message.message_id),
    )


@bot.message_handler(
    text=[
        '❌ Удалить склад/СЦ',
    ],
)
async def del_my_warehouse(message: types.Message, state: StateContext):
    if not db.read_orders(message.chat.id):
        msg = 'Вы не отслеживайте ни один склад!'
        await bot.send_message(message.from_user.id, msg, reply_markup=get_menu_buttons('📦 Мои склады'))
        return
    await state.set(DelWarehouseStates.name)
    await bot.send_message(
        message.chat.id,
        '📦 Введите название склада/СЦ',
        reply_parameters=ReplyParameters(message_id=message.message_id),
    )


@bot.message_handler(
    text=[
        '🔍 Показать все склады',
        '🔍 Показать все СЦ',
        '🔍 Показать доступные склады',
        '🔍 Показать доступные СЦ',
    ],
)
async def wb_warehouse(message: types.Message, state: StateContext):
    if message.text == '🔍 Показать все склады':
        warehouses_list = db.read_warehouses('^(?!СЦ)')
        msg = get_all_warehouse_from_list(warehouses_list, prefix='📦:')
    elif message.text == '🔍 Показать все СЦ':
        warehouses_list = db.read_warehouses('^(СЦ)')
        msg = get_all_warehouse_from_list(warehouses_list, prefix='📦:')
    elif message.text == '🔍 Показать доступные склады':
        warehouses_list = db.read_accessible_warehouses('^(?!СЦ)')
        msg = get_accept_warehouse_from_list(warehouses_list)
    elif message.text == '🔍 Показать доступные СЦ':
        warehouses_list = db.read_accessible_warehouses('^(СЦ)')
        msg = get_accept_warehouse_from_list(warehouses_list)
    if not msg:
        msg = 'Ой! Ничего не нашли по вашему запросу!'
    await bot.send_message(
        message.from_user.id,
        msg,
        reply_markup=get_menu_buttons('🍒 Склады WB'),
    )


@bot.message_handler(
    text=[
        '🔍 Найти слот',
    ],
)
async def find_slot(message: types.Message, state: StateContext):
    await state.set(FindSlot.accept_type)

    keyboard = types.ReplyKeyboardMarkup(row_width=1)
    buttons = [types.KeyboardButton(accept_type) for accept_type in ACCEPT_TYPES]
    keyboard.add(*buttons)

    await bot.send_message(
        message.from_user.id,
        'Выберите тип поставки:',
        reply_markup=keyboard,
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
        await state.add_data(warehouse_id=db.read_warehouse_id(warehouse))

        await state.set(AddWarehouseStates.max_coef)
        await bot.send_message(
            message.chat.id,
            'Укажите максимальный коэфициент приёмки от 0 до 20.',
            reply_parameters=ReplyParameters(message_id=message.message_id),
        )
    except Exception as error:
        logging.warning(f'Add warehouse to order error: {error}')
        await bot.send_message(
            message.chat.id,
            'Ой, кажется всё сломалось! Чип и дейл уже спешат на помощь!',
            reply_markup=get_menu_buttons('📦 Мои склады'),
            reply_parameters=ReplyParameters(message_id=message.message_id),
        )


@bot.message_handler(state=AddWarehouseStates.max_coef)
async def warehouse_coef_get(message: types.Message, state: StateContext):
    try:
        try:
            max_coef = int(message.text)
        except ValueError:
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
            'Через сколько календарный дней от текущей даты начинаем искать слоты?',
            reply_parameters=ReplyParameters(message_id=message.message_id),
        )
    except Exception as error:
        logging.warning(f'Add coef to order error: {error}')
        await bot.send_message(
            message.chat.id,
            'Ой, кажется всё сломалось! Чип и дейл уже спешат на помощь!',
            reply_markup=get_menu_buttons('📦 Мои склады'),
            reply_parameters=ReplyParameters(message_id=message.message_id),
        )


@bot.message_handler(state=AddWarehouseStates.delay)
async def warehouse_delay_get(message: types.Message, state: StateContext):
    try:
        try:
            delay = int(message.text)
        except ValueError:
            await bot.send_message(
                message.chat.id,
                'В ответе должно быть число. Через сколько календарных дней от текущей даты начинаем искать слоты?',
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
        logging.warning(f'Add delay to order error: {error}')
        await bot.send_message(
            message.chat.id,
            'Ой, кажется всё сломалось! Чип и дейл уже спешат на помощь!',
            reply_markup=get_menu_buttons('📦 Мои склады'),
            reply_parameters=ReplyParameters(message_id=message.message_id),
        )


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
            warehouse_id = data.get('warehouse_id')
            max_coef = data.get('max_coef')
            delay = data.get('delay')
            accept_type = data.get('accept_type')
            db.create_order(message.chat.id, warehouse_id, max_coef, delay, accept_type)
            msg = (
                f'Создана заявка на отслеживание: склад - {name}, '
                f'максимальный коэф приемки - {max_coef}, '
                f'смотрим слоты через {delay} дней, '
                f'тип поставки - {accept_type}. '
            )
        await bot.send_message(
            message.chat.id,
            msg,
            reply_markup=get_menu_buttons('📦 Мои склады'),
            reply_parameters=ReplyParameters(message_id=message.message_id),
        )
        await state.delete()
    except Exception as error:
        logging.warning(f'Add warehouse to order error: {error}')
        await bot.send_message(
            message.chat.id,
            'Ой, кажется всё сломалось! Чип и дейл уже спешат на помощь!',
            reply_markup=get_menu_buttons('📦 Мои склады'),
            reply_parameters=ReplyParameters(message_id=message.message_id),
        )


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
            reply_markup=get_menu_buttons('📦 Мои склады'),
        )
    except Exception as error:
        logging.warning(f'Delete warehouse from order error: {error}')
        await bot.send_message(
            message.chat.id,
            'Ой, кажется всё сломалось! Чип и дейл уже спешат на помощь!',
            reply_markup=get_menu_buttons('📦 Мои склады'),
            reply_parameters=ReplyParameters(message_id=message.message_id),
        )


@bot.message_handler(state=FindSlot.accept_type)
async def warehouse_find_accept_type(message: types.Message, state: StateContext):
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

        await state.set(FindSlot.delay)
        await bot.send_message(
            message.chat.id,
            'Через сколько календарных дней ищем слот?',
            reply_parameters=ReplyParameters(message_id=message.message_id),
        )
    except Exception as error:
        logging.warning(f'Find slot accept type error: {error}')
        await bot.send_message(
            message.chat.id,
            'Ой, кажется всё сломалось! Чип и дейл уже спешат на помощь!',
            reply_markup=get_menu_buttons(),
            reply_parameters=ReplyParameters(message_id=message.message_id),
        )


@bot.message_handler(state=FindSlot.delay)
async def warehouse_find_accept_coef(message: types.Message, state: StateContext):
    try:
        try:
            delay = int(message.text)
        except ValueError:
            await bot.send_message(
                message.chat.id,
                'В ответе должно быть число. Через сколько календарных дней от текущей даты начинаем искать слоты?',
                reply_parameters=ReplyParameters(message_id=message.message_id),
            )
            return
        await state.add_data(delay=delay)
        await state.set(FindSlot.max_coef)
        await bot.send_message(
            message.chat.id,
            'Укажите максимальный коэфициент приёмки от 0 до 20?',
            reply_parameters=ReplyParameters(message_id=message.message_id),
        )
    except Exception as error:
        logging.warning(f'Find slot accept coef error: {error}')
        await bot.send_message(
            message.chat.id,
            'Ой, кажется всё сломалось! Чип и дейл уже спешат на помощь!',
            reply_markup=get_menu_buttons(),
            reply_parameters=ReplyParameters(message_id=message.message_id),
        )


@bot.message_handler(state=FindSlot.max_coef)
async def warehouse_find_result(message: types.Message, state: StateContext):
    try:
        try:
            max_coef = int(message.text)
        except ValueError:
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

        async with state.data() as data:
            delay = data.get('delay')
            accept_type = data.get('accept_type')
            max_coef = data.get('max_coef')
            result = db.find_slot(max_coef, delay, accept_type)
            msg = get_slots_from_list(result)
        if not msg:
            msg = 'Ой! Ничего не нашли по вашему запросу!'
        # if len(msg) > 4096:
        for indx in range(0, len(msg), 4096):
            await bot.send_message(
                message.chat.id,
                msg[indx : indx + 4096],
                reply_markup=get_menu_buttons(),
                reply_parameters=ReplyParameters(message_id=message.message_id),
            )
        # else:
        #     await bot.send_message(
        #         message.chat.id,
        #         msg,
        #         reply_markup=get_menu_buttons(),
        #         reply_parameters=ReplyParameters(message_id=message.message_id),
        #     )
        await state.delete()
    except Exception as error:
        logging.warning(f'Find slot result error: {error}')
        await bot.send_message(
            message.chat.id,
            'Ой, кажется всё сломалось! Чип и дейл уже спешат на помощь!',
            reply_markup=get_menu_buttons(),
            reply_parameters=ReplyParameters(message_id=message.message_id),
        )


async def send_message_to_user(messages):
    for key in list(messages.keys()):
        chat_id = key
        text = messages.get(key)
        await bot.send_message(chat_id, text)


def get_all_warehouse_from_list(warehouse_list, prefix='', postfix=''):
    msg = ''
    for row in warehouse_list:
        msg += f'{prefix} {row} {postfix}\n'
    return msg


def get_accept_warehouse_from_list(warehouse_list, prefix='', postfix=''):
    msg = ''
    for row in warehouse_list:
        accept_type, warehose_name, acceptance_coef_min, acceptance_coef_max = row
        msg += f'{prefix} '
        msg += f'📦: {accept_type}, '
        msg += f'🚛: {warehose_name}, '
        msg += f'₽: {acceptance_coef_min}-{acceptance_coef_max} '
        msg += f'{postfix}\n'
    return msg


def get_slots_from_list(warehouse_list, prefix='', postfix=''):
    msg = ''
    for row in warehouse_list:
        warehose_name, acceptance_date, acceptance_coef = row
        msg += f'{prefix} '
        msg += f'📦: {warehose_name}, '
        msg += f'🚛: {acceptance_date.strftime("%d.%m.%Y")}, '
        msg += f'₽: {acceptance_coef} '
        msg += f'{postfix}\n'
    return msg


def get_orders_from_list(orders):
    msg = ''
    for order in orders:
        warehose_name, acceptance_coef_max, acceptance_delay, acceptance_type = order
        msg += f'Склад: {warehose_name}, '
        msg += f'макс. коэф. приемки {acceptance_coef_max}, '
        msg += f'смотрим слоты через {acceptance_delay} дн., '
        msg += f'тип поставки - {acceptance_type}\n'
    return msg


def get_msg_from_result(slots):
    result = {}
    for slot in slots:
        user_id, warehose_name, acceptance_date, acceptance_coef, acceptance_type = slot
        msg = result.get(user_id, '')
        msg += f'Склад: {warehose_name}, '
        msg += f'дата приемки: {acceptance_date.strftime("%d.%m.%Y")}, '
        msg += f'коэф. приемки: {acceptance_coef}, '
        msg += f'тип поставки: {acceptance_type}.\n'
        result[user_id] = msg
    return result


async def main():
    # await bot.set_my_commands(
    #     [
    #         BotCommand('/start', 'Main menu'),
    #     ],
    # )

    bot.add_custom_filter(asyncio_filters.StateFilter(bot))
    bot.add_custom_filter(asyncio_filters.TextMatchFilter())
    bot.setup_middleware(StateMiddleware(bot))
    asyncio.create_task(bot.polling())

    # заполнение таблицы warehouses
    db.create_warehouses(wb.get_warehouses())

    # пустой лист для сохранения предыдущего состояния между циклами
    previous_result = []

    while True:
        try:
            pass
            # извлекаем коэффициенты по складам
            coefficients = wb.get_coefficients()
        except MyError:
            logging.warning('Get coefficients error. Get timeout for 10 seconds.')
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
