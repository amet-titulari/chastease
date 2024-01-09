import requests
import logging
import time

from benutzer.models import Benutzer
from datetime import datetime, timedelta

from flask import session, current_app
from flask_login import current_user

# LockAPI


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
        new_tokens = response.json()

        # Überprüfen der Antwort
        if response.status_code == 200:
            new_tokens = response.json()

            session['ttl_access_token'] = new_tokens['access_token']
            session['ttl_refresh_token'] = new_tokens['refresh_token']
            session['ttl_token_expiration_time'] = datetime.now() + timedelta(seconds=new_tokens['expires_in'])
            return {'success': True}
        
    except requests.exceptions.RequestException as e:
        # Hier könnten Sie detailliertere Fehlermeldungen basierend auf dem spezifischen Fehler hinzufügen
        return {'success': False, 'error': f' {str(e)}'}

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
        return {'success': False, 'data': response.text}

    return {'success': True, 'data': result}

def open_ttlock():
    print('Oeffnen gestartet!')
    benutzer = Benutzer.query.filter_by(id=current_user.id).first()
    print(benutzer.__dict__)

#try:
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
