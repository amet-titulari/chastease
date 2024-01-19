import requests

from database import db
from helper.log_config import logger

from flask import current_app, session
from flask_login import current_user




def get_session_auth_info(main_token):


        url = f'https://api.chaster.app/api/extensions/auth/sessions/{main_token}'
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
            
            return {'success': True, 'data': result}

        except requests.exceptions.RequestException as e:
            # Hier könnten Sie detailliertere Fehlermeldungen basierend auf dem spezifischen Fehler hinzufügen
            return {'success': False, 'error': f'Fehler: {str(e)}'}
        


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
            
            return {'success': True, 'data': result}

        except requests.exceptions.RequestException as e:
            # Hier könnten Sie detailliertere Fehlermeldungen basierend auf dem spezifischen Fehler hinzufügen
            return {'success': False, 'error': f'Fehler: {str(e)}'}
        
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

        return {'success': False, 'error': f'ERROR: {str(e)}'} 

