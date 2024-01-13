import requests
import logging
import time

from benutzer.models import Benutzer
from benutzer.token_handling import is_ttl_token_valid

from flask import session, current_app, flash, redirect, url_for
from flask_login import current_user

# LockAPI

def get_lock_list(client_id, access_token):
    check = is_ttl_token_valid()
    if check:

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
            return {'success': False, 'data': response.text}

        return {'success': True, 'data': result}

def get_lock_detail(client_id, access_token):
    check = is_ttl_token_valid()
    if check:

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
            return {'success': False, 'data': response.text}

        return {'success': True, 'data': result}

def open_ttlock():
    check = is_ttl_token_valid()
    if check:

        benutzer = Benutzer.query.filter_by(id=current_user.id).first()

        timestampMS = int(time.time() * 1000)
        url = f"https://euapi.ttlock.com/v3/lock/unlock"
        params = {
            "clientId": current_app.config['TTL_CLIENT_ID'],
            "accessToken": session['ttl_access_token'],
            "lockId": benutzer.TTL_lock_id,
            "date": timestampMS
        }

        response = requests.get(url, params=params)
        
        if response.status_code == 200:
            return response.json()
        elif response.status_code == 401:  # Oder welcher Statuscode auch immer für ungültige Tokens steht
            return "Token ungültig"
        else:
            logging.error(f"Fehler beim Öffnen des Schlosses: {response.text}")
            return None
