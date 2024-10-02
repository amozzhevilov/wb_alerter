import requests
from time import sleep

class wb:

    def __init__(self, token) -> None:
        self.token = token # TOKEN доступ до API

    def get_coefficients (self):
        
        url = 'https://supplies-api.wildberries.ru/api/v1/acceptance/coefficients'
        headers = {'Authorization':self.token}

        try:
            x = requests.get(url, headers=headers)
        except:
            print("Failed to get request")
            return(-1)
        else:
            return(x)
        
    def get_warehouses (self):
        
        url = 'https://supplies-api.wildberries.ru/api/v1/warehouses'
        headers = {'Authorization':self.token}

        try:
            x = requests.get(url, headers=headers)
        except:
            print("Failed to get request")
            return(-1)
        else:
            return(x)
        
            
