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
            
            return {'success': True, 'session': result}

        except requests.exceptions.RequestException as e:
            # Hier könnten Sie detailliertere Fehlermeldungen basierend auf dem spezifischen Fehler hinzufügen
            return {'success': False, 'error': f'Fehler: {str(e)}'}

    except requests.exceptions.RequestException as e:
        # Hier könnten Sie detailliertere Fehlermeldungen basierend auf dem spezifischen Fehler hinzufügen

        return {'success': False, 'error': f'ERROR: {str(e)}'} 

def get_config_info(token):
    try:
        # URL für die API-Anfrage
        url = f'https://api.chaster.app/api/extensions/configurations/{token}'


        # HTTP-Header setzen, in diesem Fall nur den 'accept'-Header
        headers = {
            'accept': 'application/json',
            'Authorization': f'Bearer {current_app.config['CA_DEV_TOKEN']}'
        }

        # Die GET-Anfrage durchführen
        response = requests.get(url, headers=headers)

        # Prüfen, ob die Anfrage erfolgreich war
        if response.status_code == 200:
            # Die Antwort als JSON-Objekt bekommen
            data = response.json()
                        
            # Daten extrahieren
            session_id = data['sessionId']
            sessioninfo = get_session_info(session_id)

            if sessioninfo['success']:
                session = sessioninfo['session']
                return {'success': True, 'session': session} 
            else:
                return {'success': False, 'error': f'ERROR: {str(e)}'} 

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

    