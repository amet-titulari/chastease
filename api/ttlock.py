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

import requests

def get_ttlock_tokens(client_id, client_secret, username, password):
    print(f'ClientID: {client_id} \t ClientSec: {client_secret} \t User: {username} \t Pass: {password}')

    url = 'https://euapi.ttlock.com/oauth2/token'
    headers = {'Content-Type': 'application/x-www-form-urlencoded'}
    data = {
        'clientId': client_id,
        'clientSecret': client_secret,
        'username': username,
        'password': password
    }

    try:
        response = requests.post(url, headers=headers, data=data)
        response.raise_for_status()  # Löst eine Ausnahme aus, wenn der HTTP-Statuscode 4xx oder 5xx ist

        # Hier könnte zusätzlich geprüft werden, ob die Antwort einen spezifischen Fehlercode enthält
        result = response.json()
        if 'errcode' in result and result['errcode'] != 0:
            return {'success': False, 'error': result.get('errmsg', 'Unbekannter Fehler')}

        return {'success': True, 'data': result}

    except requests.exceptions.RequestException as e:
        # Hier könnten Sie detailliertere Fehlermeldungen basierend auf dem spezifischen Fehler hinzufügen
        return {'success': False, 'error': f'Netzwerk- oder HTTP-Fehler: {str(e)}'}


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
