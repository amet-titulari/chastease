import requests
import logging
import time
import datetime

from dateutil import parser

from benutzer.models import Benutzer, LockHistory
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


def get_ttlock_records():

    # Infos zu Lock Records:
    # https://euopen.ttlock.com/document/doc?urlName=cloud%2FlockRecord%2FlistEn.html

    # --> Damit kann sichergestellt werden, dass öffnen wie Bluetooth Bestraft werden kann
    # --> recordTypeFromLock = 1 (unlock by Bluetooth) und recordtype = 1 (unlock by app)
    # --> öffnungen dürfen nur noch mit folgendem Eintrag erfolgen
    # --> recordTypeFromLock = 28 (unlock by gateway) und recordtyp = 12 (unlock by gateway)

    # Überprüfen, ob das Token gültig ist
    check = is_ttl_token_valid()
    if not check:
        return "Token ungültig oder abgelaufen"

    benutzer = Benutzer.query.filter_by(id=current_user.id).first()
    start_date_lock = LockHistory.query.filter(
        LockHistory.description == "New lock started", 
        LockHistory.benutzer_id == current_user.id
        ).order_by(LockHistory.created_at).first()

    print(start_date_lock.created_at)

    start_date_db = start_date_lock.created_at


    start_date_sec = parser.isoparse(start_date_db)


    timestamp_start_seconds = start_date_sec.timestamp()
    start_date              = int(timestamp_start_seconds * 1000)
    end_date                = int(time.time() * 1000)

    print(start_date, end_date)


    url = "https://euapi.ttlock.com/v3/lockRecord/list"

    # Definieren Sie die Start- und Enddaten für die Aufzeichnungen

    params = {
        "clientId": current_app.config['TTL_CLIENT_ID'],
        "accessToken": session['ttl_access_token'],
        "lockId": benutzer.TTL_lock_id,
        "startDate": start_date,
        "endDate": end_date,
        "pageNo": 1,
        "pageSize": 100,
        "date": int(time.time() * 1000)  # Aktuelles Datum in Millisekunden
    }

    history = requests.get(url, params=params)

    print(history.json())

    if history.status_code == 200:
        return {'success': True, 'data': f'{history}'}
    elif history.status_code == 401:
        return {'success': False, 'data': f'Fehler aufgetgreten'}
    else:
        print(f"Fehler beim Abrufen der Schlossaufzeichnungen: {history.text}")
        return None