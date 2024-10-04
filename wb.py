'''API for WB'''
import requests

class WB:
    '''Class for WB API'''

    def __init__(self, token) -> None:
        self.token = token # TOKEN доступ до API

    def get_coefficients (self):
        '''Get warehouse coefficients'''
        url = 'https://supplies-api.wildberries.ru/api/v1/acceptance/coefficients'
        headers = {'Authorization':self.token}

        try:
            x = requests.get(url, headers=headers, timeout=10)
        except requests.exceptions.RequestException as err:
            print("OOps: Something error",err)
            return -1

        return x

    def get_warehouses (self):
        '''Get list of warehouse'''
        url = 'https://supplies-api.wildberries.ru/api/v1/warehouses'
        headers = {'Authorization':self.token}

        try:
            x = requests.get(url, headers=headers, timeout=10)
        except requests.exceptions.RequestException as err:
            print("OOps: Something error",err)
            return -1

        return x
