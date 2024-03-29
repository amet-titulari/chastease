import os
import requests
import logging
import time
import json

from datetime import datetime
from dateutil import parser
from database import db

from benutzer.models import Benutzer, History_TTLock, History_Chaster
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

def get_gateway_list(client_id, access_token):
    check = is_ttl_token_valid()
    if check:

        timestampMS = int(time.time() * 1000)
        url = "https://euapi.ttlock.com/v3/gateway/list"
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
    #check = is_ttl_token_valid()
    #if check:

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

def get_ttlock_history():

    check = is_ttl_token_valid()
    if not check:
        return "Token ungültig oder abgelaufen"

    benutzer = Benutzer.query.filter_by(id=current_user.id).first()
    start_date_lock = History_Chaster.query.filter(
        History_Chaster.description == "New lock started", 
        History_Chaster.benutzer_id == current_user.id
        ).order_by(History_Chaster.created_at).first()
    


    start_date_db = start_date_lock.created_at
    start_date_sec = parser.isoparse(start_date_db)

    timestamp_start_seconds = start_date_sec.timestamp()
    start_date              = int(timestamp_start_seconds * 1000)
    end_date                = int(time.time() * 1000)

    # Laden der Konfigurationsdaten
    #print(os.getcwd())

    url = "https://euapi.ttlock.com/v3/lockRecord/list"

    current_page = 1
    total_pages  = 999

    params = {
        "clientId": current_app.config['TTL_CLIENT_ID'],
        "accessToken": session['ttl_access_token'],
        "lockId": benutzer.TTL_lock_id,
        "startDate": start_date,
        "endDate": end_date,
        "pageNo": current_page,
        "pageSize": 25,
        "date": int(time.time() * 1000)  # Aktuelles Datum in Millisekunden
    }

    with open('api/ttlock_codes.json', 'r') as file:
        codes = json.load(file)


    while current_page <= total_pages:

               
        response = requests.get(url, params=params)
        if response.status_code == 200:
            
            history = response.json()
            total_pages = history['pages']
            #print(f'Seite : {params['pageNo']} von insgesammt {total_pages} Seiten')

            for result in history['list']:
                hist_id = result.get('recordId')

                existing_entry = History_TTLock.query.filter_by(hist_id=hist_id).first()

                if not existing_entry:
                    # Eintragsdatum ermitteln
                    lockDate_milliseconds = result.get('lockDate')
                    lockDate_seconds = lockDate_milliseconds / 1000
                    lockDate_datetime = datetime.fromtimestamp(lockDate_seconds)
                    formatted_lockDate = lockDate_datetime.strftime('%Y-%m-%d %H:%M:%S')

                    # Recordtype und RecordTypeFromLock erstellen
                    recordtype = result.get('recordType')
                    recordtypefromlock = result.get('recordTypeFromLock')
                    # Zuordnung der Texte aus dem Wörterbuch und Konvertierung der Integer-Werte zu Strings für den Schlüsselzugriff
                    recordtype_str = codes['recordtype_mapping'].get(str(recordtype), "Unbekannter Typ")
                    recordtypefromlock_str = codes['recordtypelock_mapping'].get(str(recordtypefromlock), "Unbekannter Typ")

                    # Eintrag erstellen
                    new_history_entry = History_TTLock(
                            benutzer_id=current_user.id,
                            hist_id=hist_id,
                            lock_id=result.get('lockId'),
                            type="TTL Lock Protokol",
                            created_at=formatted_lockDate,
                            recordtyp=recordtype,
                            recordtypstr=recordtype_str,
                            recordtypefromlock=recordtypefromlock,
                            recordtypefromlockstr=recordtypefromlock_str,
                            openSuccess=result.get('success')
                        )
                    
                    db.session.add(new_history_entry)
                else:
                    #print("Eintrag existiert")
                    pass
            
            db.session.commit()
            current_page += 1

        else:
            print(f"Fehler beim Abrufen der Schlossaufzeichnungen: {history.text}")
            return None
    
    return {'success': True}

def tranfer_ttlock():
    check = is_ttl_token_valid()
    if check:

        pass