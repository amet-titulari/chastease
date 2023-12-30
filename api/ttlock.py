import os
import requests

# LockAPI
def get_lock_list(self, page_no=1, page_size=20, date=None):
    url = f'{self.base_url}/lock/list'
    params = {
        'clientId': self.client_id,
        'accessToken': self.access_token,
        'pageNo': page_no,
        'pageSize': page_size,
        'date': date
    }
    response = requests.get(url, params=params)
    return response.json()

def get_lock_detail(self, page_no=1, page_size=20, date=None):
    url = f'{self.base_url}/lock/list'
    params = {
        'clientId': self.client_id,
        'accessToken': self.access_token,
        'pageNo': page_no,
        'pageSize': page_size,
        'date': date
    }
    response = requests.get(url, params=params)
    return response.json()

# OAUTH
def get_ttlock_tokens(client_id, client_secret, username, password):
    url = 'https://euapi.ttlock.com/oauth2/token'
    headers = {'Content-Type': 'application/x-www-form-urlencoded'}
    data = {
        'clientId': client_id,
        'clientSecret': client_secret,
        'username': username,
        'password': password
    }
    response = requests.post(url, headers=headers, data=data)
    return response.json()

def refresh_ttlock_tokens(client_id, client_secret, refresh_tocken):
    url = 'https://euapi.ttlock.com/oauth2/token'
    headers = {'Content-Type': 'application/x-www-form-urlencoded'}
    data = {
        'clientId': client_id,
        'clientSecret': client_secret,
        'grant_type': 'refresh_tocken',
        'refresh_token': refresh_tocken
    }
    response = requests.post(url, headers=headers, data=data)
    return response.json()