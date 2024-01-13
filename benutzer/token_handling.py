import time
import requests

from flask import session, current_app, flash, redirect, url_for
from flask_login import current_user


from benutzer.models import Benutzer

from helper.log_config import logger

def is_ca_token_valid():
    if current_user.is_authenticated:
        try:
            expiration_time = session['ca_token_expiration_time']
        except KeyError:
            # Schlüssel ist nicht vorhanden, behandeln Sie den Fehler
            expiration_time = 0

        # Zeitpunkt in 5 Minuten
        time_in_5_minutes = time.time() + (5 * 60)

        # Prüfen, ob das Token in den nächsten 5 Minuten abläuft
        print(f'\nSession\t\t: {expiration_time} \nPrüfung 5min\t: {time_in_5_minutes}\n\n')
        
        if expiration_time < time_in_5_minutes:
            response = refresh_ca_token()
            return bool(response)
        else:
            return True
    else:
        return redirect(url_for('login'))

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
        session['ca_token_expiration_time'] = time.time() + new_tokens['expires_in']
        return True
    else:
        # Fehlerbehandlung
        return False

def is_ttl_token_valid():
    try:
        expiration_time = session['ttl_token_expiration_time']
    except KeyError:
        TT_lock_tokens = get_ttlock_tokens()

    if current_user.is_authenticated:
        # Zeitpunkt in 5 Minuten
        time_in_5_minutes = time.time() + (5 * 60)

        # Prüfen, ob das Token in den nächsten 5 Minuten abläuft
        print(f'\nSession\t\t: {expiration_time} \nPrüfung 5min\t: {time_in_5_minutes}\n\n')
        if expiration_time < time_in_5_minutes:
            response = refresh_ttl_token()
            return bool(response)
        else:
            return True
    else:
        return redirect(url_for('login'))

def get_ttlock_tokens():
   

        benutzer = Benutzer.query.filter_by(id=current_user.id).first()

        if not benutzer.TTL_username or not benutzer.TTL_password_md5:
            flash('Benutzername oder Passwort für TTLock fehlt. Bitte aktualisieren Sie Ihre Konfiguration.', 'warning')
            return redirect(url_for('benutzer.config'))

        client_id       = current_app.config['TTL_CLIENT_ID']
        client_secret   = current_app.config['TTL_CLIENT_SECRET']
        username        = benutzer.TTL_username
        password        = benutzer.TTL_password_md5

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

            if response.status_code == 200:
                new_tokens = response.json()

                # Überprüfen, ob die Antwort einen Fehler enthält
                if 'errcode' in new_tokens:
                    error_message = new_tokens.get('errmsg', 'Ein unbekannter Fehler ist aufgetreten.')
                    flash(f'TTLock Config: {error_message}', 'danger')  # Zeigt die Fehlermeldung als Flash-Nachricht an
                    return {'success': False, 'error': error_message}

                # Kein Fehler, setze die Tokens und Zeiten
                session['ttl_access_token'] = new_tokens['access_token']
                session['ttl_refresh_token'] = new_tokens['refresh_token']
                session['ttl_token_expiration_time'] = time.time() + new_tokens['expires_in']
                return {'success': True}
            
        except requests.exceptions.RequestException as e:
            # Hier könnten Sie detailliertere Fehlermeldungen basierend auf dem spezifischen Fehler hinzufügen
            return {'success': False, 'error': f' {str(e)}'}

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
            session['ttl_token_expiration_time'] = time.time() + new_tokens['expires_in']
            return True
    except:
        return False


