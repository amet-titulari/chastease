import requests

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
