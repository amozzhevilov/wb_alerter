'''API for WB'''
import requests

CONNECT_TIMEOUT = 10
SUPPLIES_API = 'https://supplies-api.wildberries.ru/api/v1'

class MyError(Exception):
    '''Class for exception'''
    pass

class WB:
    '''Class for WB API'''

    def __init__(self, token) -> None:
        self.token = token # TOKEN доступ до API

    def get_coefficients (self):
        '''Get warehouse coefficients'''
        url = f'{SUPPLIES_API}/acceptance/coefficients'
        headers = {'Authorization':self.token}
        data = ''

        try:
            #  Выполняем запрос
            response = requests.get(url, headers=headers, timeout=CONNECT_TIMEOUT)

            # Обработка ответа
            if response.status_code == 200:
                data = response.json()
            else:
                print(f'Get wrong status code: {response.status_code}')
                raise MyError(f'Get wrong status code: {response.status_code}')

        except requests.exceptions.RequestException as err:
            raise MyError(f'Request got wrong: {err}') from err

        return data

    def get_warehouses (self):
        '''Get list of warehouse'''
        url = f'{SUPPLIES_API}/warehouses'
        headers = {'Authorization':self.token}

        try:
            x = requests.get(url, headers=headers, timeout=CONNECT_TIMEOUT)
        except requests.exceptions.RequestException as err:
            print("OOps: Something error",err)
            return -1

        return x
