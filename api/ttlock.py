import os
import time
import requests
import logging

from flask import session

# LockAPI
def get_lock_list(client_id, access_token):
    timestampMS = int(time.time() * 1000)
    url = "https://euapi.ttlock.com/v3/lock/list"
    params = {
        'clientId': client_id,
        'accessToken': access_token,
        'pageNo': 1,
        'pageSize': 20,
        'date': timestampMS
    }
    response = requests.get(url, params=params)

    if response.status_code == 200:
        # Versuchen, die Antwort als JSON zu interpretieren
        result = response.json()
    else:
        print(f"Fehler: HTTP-Status {response.status_code}")
        print(response.text)  # Gibt den Text der Antwort aus, der hilfreich sein kann
        return {'success': False, 'data': response.text}

    return {'success': True, 'data': result}

def get_lock_detail(client_id, access_token):
    timestampMS = int(time.time() * 1000)
    url = 'https://euapi.ttlock.com/v3/lock/detail'
    params = {
        'clientId': client_id,
        'accessToken': access_token,
        'pageNo': 1,
        'pageSize': 20,
        'date': timestampMS
    }
    response = requests.get(url, params=params)

    if response.status_code == 200:
        # Versuchen, die Antwort als JSON zu interpretieren
        result = response.json()
    else:
        print(f"Fehler: HTTP-Status {response.status_code}")
        print(response.text)  # Gibt den Text der Antwort aus, der hilfreich sein kann
        return {'success': False, 'data': response.text}

    return {'success': True, 'data': result}

import requests

def get_ttlock_tokens(client_id, client_secret, username, password):

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


def open_ttlock(TTL_client_id, TTL_access_token, TTL_lock_id):

    try:
        timestampMS = int(time.time() * 1000)
        url = f"https://euapi.ttlock.com/v3/lock/unlock"
        params = {
            "clientId": TTL_client_id,
            "accessToken": TTL_access_token,
            "lockId": TTL_lock_id,
            "date": timestampMS
        }

        response = requests.get(url, params=params)

        print(f'Debug Info: {response.status_code}')
        
        if response.status_code == 200:
            return response.json()
        elif response.status_code == 401:  # Oder welcher Statuscode auch immer für ungültige Tokens steht
            return "Token ungültig"
        else:
            logging.error(f"Fehler beim Öffnen des Schlosses: {response.text}")
            return None
    except requests.RequestException as e:
        logging.error(f"Netzwerk- oder HTTP-Fehler: {e}")
        return None