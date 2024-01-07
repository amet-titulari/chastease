import requests
from flask import session, current_app
from datetime import datetime, timedelta

def is_token_expiring_soon():
    expiration_time = session.get('token_expiration_time')
    if expiration_time is None:
        return False

    # Überprüfen, ob das Token innerhalb der nächsten 5 Minuten abläuft
    return datetime.now() >= (expiration_time - timedelta(minutes=5))

def refresh_token():
    # Setzen Sie Ihre Client-ID und das Client-Secret hier


    client_id = current_app.config['CA_CLIENT_ID']
    client_secret = current_app.config['CA_CLIENT_SECRET']

    # URL des Token-Endpunkts des OAuth2-Anbieters
    token_url = 'https://sso.chaster.app/auth/realms/app/protocol/openid-connect/token'

    # Holen Sie sich das Refresh Token aus der Session (oder einer anderen Quelle)
    refresh_token = session.get('refresh_token')

    # Stellen Sie sicher, dass das Refresh Token vorhanden ist
    if refresh_token is None:
        # Behandeln Sie den Fall, dass kein Refresh Token vorhanden ist
        return False

    # Daten für die POST-Anfrage
    data = {
        'client_id': client_id,
        'client_secret': client_secret,
        'grant_type': 'refresh_token',
        'refresh_token': refresh_token
    }

    # Senden der Anfrage
    response = requests.post(token_url, data=data)

    # Überprüfen der Antwort
    if response.status_code == 200:
        new_tokens = response.json()
        session['access_token'] = new_tokens['access_token']
        session['refresh_token'] = new_tokens.get('refresh_token', refresh_token)
        session['token_expiration_time'] = datetime.now() + timedelta(seconds=new_tokens['expires_in'])
        return True
    else:
        # Fehlerbehandlung
        return False

def check_and_refresh_token():
    if is_token_expiring_soon():
        return refresh_token()
    return False
