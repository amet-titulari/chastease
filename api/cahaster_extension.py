import requests

from database import db
from helper.log_config import logger

from flask import current_app, session
from flask_login import current_user




from flask import current_app
import requests

def get_session_auth_info(main_token):
    # Beachten Sie die Änderung in der Verwendung der Anführungszeichen im Authorization-Header
    url = f"https://api.chaster.app/api/extensions/auth/sessions/{main_token}"
    headers = {
        'Authorization': f"Bearer {current_app.config['CA_DEV_TOKEN']}"
    }

    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()  # Löst eine Ausnahme aus, wenn der HTTP-Statuscode 4xx oder 5xx ist

        result = response.json()

        # Überprüfen Sie hier, ob die Antwort einen spezifischen Fehlercode enthält
        if 'error' in result or 'errcode' in result and result.get('errcode') != 0:
            # Angenommen, die API gibt einen Fehlercode innerhalb der Antwort zurück
            return {'success': False, 'error': result.get('error', result.get('errmsg', 'Unbekannter Fehler'))}
        
        # Wenn alles in Ordnung ist, geben Sie die Daten zurück
        return {'success': True, 'data': result}

    except requests.exceptions.HTTPError as e:
        # Ein HTTPError könnte für 4xx oder 5xx Fehlercodes geworfen werden
        return {'success': False, 'error': f'HTTP-Fehler: {str(e)}'}
    except requests.exceptions.RequestException as e:
        # Andere Arten von Fehlern (Netzwerkfehler, etc.)
        return {'success': False, 'error': f'Netzwerkfehler: {str(e)}'}

def get_session_info(sessionId):

    try:

        url = f'https://api.chaster.app/api/extensions/sessions/{sessionId}'
        headers = {
            'Authorization': f'Bearer {current_app.config['CA_DEV_TOKEN']}'
        }


        try:
            response = requests.get(url,headers=headers)
            response.raise_for_status()  # Löst eine Ausnahme aus, wenn der HTTP-Statuscode 4xx oder 5xx ist

            result = response.json()
            # Überprüfen Sie hier, ob die Antwort einen spezifischen Fehlercode enthält
            if 'errcode' in result and result['errcode'] != 0:
                return {'success': False, 'error': result.get('errmsg', 'Unbekannter Fehler')}

            print(result)            
            return {'success': True, 'data': result}

        
            token_response = requests.post(
                current_app.config['CA_TOKEN_ENDPOINT'],
                data={
                    'grant_type': 'authorization_code',
                    'code': code,
                    'redirect_uri': current_app.config['BASE_URL'] + 'callback',
                    'client_id': current_app.config['CA_CLIENT_ID'],
                    'client_secret': current_app.config['CA_CLIENT_SECRET']
                }
            )

            token_data = token_response.json()

            session['ca_access_token'] = token_data.get('access_token')
            session['ca_refresh_token'] = token_data.get('refresh_token')
            session['ca_token_expiration_time'] = time.time() + token_data['expires_in']

            return {'success': True}        

        except requests.exceptions.RequestException as e:
            # Hier könnten Sie detailliertere Fehlermeldungen basierend auf dem spezifischen Fehler hinzufügen
            return {'success': False, 'error': f'Fehler: {str(e)}'}

    except requests.exceptions.RequestException as e:
        # Hier könnten Sie detailliertere Fehlermeldungen basierend auf dem spezifischen Fehler hinzufügen

        return {'success': False, 'error': f'ERROR: {str(e)}'} 

def get_config_info(token):
    try:
        # URL für die API-Anfrage
        print(f'GET_CONIFG_INFO\nToken:{token}')
        url = f'https://api.chaster.app/api/extensions/configurations/{token}'
        print(f'URL: {url}')

        # HTTP-Header setzen, in diesem Fall nur den 'accept'-Header
        headers = {
            'accept': 'application/json',
        }

        # Die GET-Anfrage durchführen
        response = requests.get(url, headers=headers)
        print(f'Response: {response.json()}')

        # Prüfen, ob die Anfrage erfolgreich war
        if response.status_code == 200:
            # Die Antwort als JSON-Objekt bekommen
            data = response.json()
            print(f'Daten: {data}')
            return {'success': True, 'data': data} 
            
        else:
            try:
                # Versuchen, die Fehlermeldung aus dem Antwort-Body zu extrahieren
                error_message = response.json().get('message', 'Keine spezifische Fehlermeldung verfügbar.')
            except ValueError:
                # Falls die Antwort keinen JSON-Body hat oder nicht geparst werden kann
                error_message = response.text or 'Keine spezifische Fehlermeldung verfügbar.'
            
            print(f'Fehler bei der Anfrage: {response.status_code}, Nachricht: {error_message}')



    except requests.exceptions.RequestException as e:
        # Hier könnten Sie detailliertere Fehlermeldungen basierend auf dem spezifischen Fehler hinzufügen
        return {'success': False, 'error': f'ERROR: {str(e)}'} 

    