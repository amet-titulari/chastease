import requests

from helper.log_config import logger

from flask_login import current_user


def get_user_profile(ca_username, client_id, client_secret):
    url = f'https://api.chaster.app/users/profile/{ca_username}'
    headers = {
        'X-Chaster-Client-Id': client_id,
        'X-Chaster-Client-Secret': client_secret
    }

    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()  # Löst eine Ausnahme aus, wenn der HTTP-Statuscode 4xx oder 5xx ist

        result = response.json()
        # Überprüfen Sie hier, ob die Antwort einen spezifischen Fehlercode enthält
        if 'errcode' in result and result['errcode'] != 0:
            return {'success': False, 'error': result.get('errmsg', 'Unbekannter Fehler')}

        return {'success': True, 'data': result}

    except requests.exceptions.RequestException as e:
        # Hier könnten Sie detailliertere Fehlermeldungen basierend auf dem spezifischen Fehler hinzufügen
        return {'success': False, 'error': f'Netzwerk- oder HTTP-Fehler: {str(e)}'}

def get_user_lockid(ca_userid, client_id, client_secret):

    url = f'https://api.chaster.app/locks/user/{ca_userid}'
    headers = {
        'X-Chaster-Client-Id': client_id,
        'X-Chaster-Client-Secret': client_secret
    }

    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()  # Löst eine Ausnahme aus, wenn der HTTP-Statuscode 4xx oder 5xx ist

        result = response.json()
        # Überprüfen Sie hier, ob die Antwort einen spezifischen Fehlercode enthält
        if 'errcode' in result and result['errcode'] != 0:
            return {'success': False, 'error': result.get('errmsg', 'Unbekannter Fehler')}

        return {'success': True, 'data': result}

    except requests.exceptions.RequestException as e:
        # Hier könnten Sie detailliertere Fehlermeldungen basierend auf dem spezifischen Fehler hinzufügen
        return {'success': False, 'error': f'Netzwerk- oder HTTP-Fehler: {str(e)}'}

def get_user_lockinfo(ca_lockid, ca_access_token):
    url = f'https://api.chaster.app/locks/{ca_lockid}'
    headers = {
        'accept': 'application/json',
        'Authorization': f'Bearer {ca_access_token}'
    }

    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()  # Löst eine Ausnahme aus, wenn der HTTP-Statuscode 4xx oder 5xx ist

        result = response.json()
        # Überprüfen Sie hier, ob die Antwort einen spezifischen Fehlercode enthält
        if 'errcode' in result and result['errcode'] != 0:
            return {'success': False, 'error': result.get('errmsg', 'Unbekannter Fehler')}

        return {'success': True, 'data': result}

    except requests.exceptions.RequestException as e:
        # Hier könnten Sie detailliertere Fehlermeldungen basierend auf dem spezifischen Fehler hinzufügen
        return {'success': False, 'error': f'Netzwerk- oder HTTP-Fehler: {str(e)}'}

def upload_lock_image(ca_access_token, file_path):
    url = "https://api.chaster.app/combinations/image"

    # Header festlegen (ohne Content-Type)
    headers = {
        "accept": "application/json",
        "Authorization": f'Bearer {ca_access_token}'
    }

    # Erstellen des 'files'-Dictionary für den Upload
    with open(file_path, 'rb') as file_to_upload:
        files = {
            'file': (file_path, file_to_upload, 'image/png')
        }

        # Zusätzliche Daten
        data = {
            'enableManualCheck': 'false'
        }

        try:
            # POST-Anfrage senden
            response = requests.post(url, headers=headers, files=files, data=data)
            response.raise_for_status()  # Löst eine Exception aus, wenn der HTTP-Statuscode kein 200 ist
            result = response.json()
            return {'success': True, 'data': result}
        except requests.RequestException as e:
            # Detaillierte Fehlermeldung
            return {'success': False, 'error': f'Upload fehlgeschlagen: {str(e)}'}
        
def update_combination_relock(ca_lock_id, ca_access_token, ca_combination):
    url = f"https://api.chaster.app/extensions/temporary-opening/{ca_lock_id}/combination"

    # Header festlegen
    headers = {
        "accept": "*/*",
        "Authorization": f"Bearer {ca_access_token}",
        "Content-Type": "application/json"
    }

    # Daten für die Anfrage
    data = {
        "combinationId": ca_combination
    }


    try:
        response = requests.post(url, headers=headers, json=data)
  
        response.raise_for_status()  # Löst eine Exception aus, wenn der HTTP-Statuscode kein 200 ist
        result = response.json()
        return {'success': True, 'data': result}
    except requests.RequestException as e:
            # Detaillierte Fehlermeldung
        return {'success': False, 'error': f'Upload fehlgeschlagen: {str(e)}'}
