import datetime
import requests

from flask import session, current_app
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo  # Python 3.9 und später

from helper.log_config import logger

from api.ttlock import get_ttlock_tokens

def is_ca_token_valid():
    # Aktuelle UTC-Zeit als zeitzone-bewusstes Objekt
    current_time = datetime.now(ZoneInfo("CET"))

    # Zeitpunkt in 5 Minuten
    time_in_5_minutes = current_time + timedelta(minutes=5)

    # Prüfen, ob das Token in den nächsten 5 Minuten abläuft
    if session['ca_token_expiration_time'] >= time_in_5_minutes:
        
        response = refresh_ca_token()

        if response:
            return True
        else:
            return False
    else:
        
        return True

def is_ttl_token_valid():
    # Aktuelle UTC-Zeit als zeitzone-bewusstes Objekt
    current_time = datetime.now()

    # Zeitpunkt in 5 Minuten
    time_in_5_minutes = current_time + timedelta(minutes=5)

    # Prüfen, ob das Token in den nächsten 5 Minuten abläuft
    if session['ttl_token_expiration_time'] >= time_in_5_minutes:

        response = refresh_ttl_token()
        if response:
            return True
        else:
            return False
    else:
        return True

def refresh_ca_token():

    # URL des Token-Endpunkts des OAuth2-Anbieters
    token_url = 'https://sso.chaster.app/auth/realms/app/protocol/openid-connect/token'

    data = {
        'client_id': current_app.config['CA_CLIENT_ID'],
        'client_secret': current_app.config['CA_CLIENT_SECRET'],
        'grant_type': 'refresh_token',
        'refresh_token': session['ca_refresh_token']
    }

    # Senden der Anfrage
    response = requests.post(token_url, data=data)

    # Überprüfen der Antwort
    if response.status_code == 200:
        new_tokens = response.json()
        session['ca_access_token'] = new_tokens['access_token']
        session['ca_refresh_token'] = new_tokens['refresh_token']
        session['ca_token_expiration_time'] = datetime.now() + timedelta(seconds=new_tokens['expires_in'])
        return True
    else:
        # Fehlerbehandlung
        return False

def refresh_ttl_token():

    url = "https://euapi.ttlock.com/oauth2/token"

    headers = {
        "Content-Type": "application/x-www-form-urlencoded"
    }

    data = {
        'client_id': current_app.config['TTL_CLIENT_ID'],
        'client_secret': current_app.config['TTL_CLIENT_SECRET'],
        "grant_type": "refresh_token",
        "refresh_token": session['ttl_refresh_token']
    }

    try:
        response = requests.post(url, headers=headers, data=data)

        # Überprüfen der Antwort
        if response.status_code == 200:
            new_tokens = response.json()

            session['ttl_access_token'] = new_tokens['access_token']
            session['ttl_refresh_token'] = new_tokens['refresh_token']
            session['ttl_token_expiration_time'] = datetime.now() + timedelta(seconds=new_tokens['expires_in'])
            return True
    except:
        print(f'ERROR: {response.json()}')
        return False


