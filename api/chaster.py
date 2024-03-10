import requests
import time

from database import db

from helper.log_config import logger

from flask import current_app, session
from flask_login import current_user, login_user

from benutzer.models import Benutzer, History_Chaster
from benutzer.token_handling import is_ca_token_valid


def handler_callback(code):
    
    try:
        
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
        print(session['ca_refresh_token'])
        session['ca_token_expiration_time'] = time.time() + token_data['expires_in']

        return {'success': True}        

    except requests.exceptions.RequestException as e:
        # Hier könnten Sie detailliertere Fehlermeldungen basierend auf dem spezifischen Fehler hinzufügen

        return {'success': False, 'error': f'ERROR: {str(e)}'} 

def get_auth_userinfo():
    check = is_ca_token_valid()
    if check:

        try:
        
            user_info_url = f"{current_app.config['CA_BASE_ENDPOINT']}/auth/profile"

            user_info_response = requests.get(
                user_info_url, 
                headers={'Authorization': f'Bearer {session['ca_access_token']}'}
            )

            user_info = user_info_response.json()

            username = user_info.get('username')  # oder ein anderes relevantes Feld
            session['username'] = username
            role = user_info.get('role')  # oder ein anderes relevantes Feld
            avatarUrl = user_info.get('avatarUrl')

            benutzer = Benutzer.query.filter_by(username=username).first()
            
            if not benutzer:
                benutzer = Benutzer(username=username, role=role, avatarUrl=avatarUrl)
                benutzer.CA_refresh_token=session['ca_refresh_token']
                db.session.add(benutzer)
                db.session.commit()
                login_user(benutzer)    
                return {'success': True, 'message': f'Benutzer {username} erstellt'}
            else: 
                benutzer.username = username
                benutzer.role = role
                benutzer.avatarUrl = avatarUrl
                benutzer.CA_refresh_token=session['ca_refresh_token']    
                db.session.commit()
                login_user(benutzer)  
                return {'success': True, 'Message': f'Benutzer {username} angemeldetet'}

        except requests.exceptions.RequestException as e:
            # Hier könnten Sie detailliertere Fehlermeldungen basierend auf dem spezifischen Fehler hinzufügen

            return {'success': False, 'error': f'ERROR: {str(e)}'} 

def get_user_profile(ca_username, client_id, client_secret):

    check = is_ca_token_valid()
    if check:

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

    check = is_ca_token_valid()
    if check:

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
            return {'success': False, 'error': f'ERROR: {str(e)}'}

def get_user_lockinfo(ca_lockid, ca_access_token):

    check = is_ca_token_valid()
    if check:

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

def get_hygiene_opening(ca_lockid, ca_access_token):
    check = is_ca_token_valid()
    if check:

        try:

            url = f'https://api.chaster.app/extensions/temporary-opening/{ca_lockid}/combination'
            headers = {
                'accept': 'application/json',
                'Authorization': f'Bearer {ca_access_token}'
            }

            response = requests.get(url, headers=headers)

            result = response.json()
            #print(result)
           
            if response.status_code == 200:
                # Erfolgreiche Antwort
                return {'success': True, 'data':result}
            elif response.status_code == 400:
                # Fehlerhafte Anfrage
                return {'success': False, 'data': 'Lock not ready to open!'}
            else:
                # Andere Fehler
               return {'success': False, 'data' : 'An unexpected error occurred {response.status_code}'}
        
        except requests.exceptions.RequestException as e:
            # Hier könnten Sie detailliertere Fehlermeldungen basierend auf dem spezifischen Fehler hinzufügen
            return {'success': False, 'error': f'Netzwerk- oder HTTP-Fehler: {str(e)}'}

def upload_lock_image(ca_access_token, file_path):

    check = is_ca_token_valid()
    if check:

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

    check = is_ca_token_valid()
    if check:

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

def get_chaster_history():
    check = is_ca_token_valid()
    if check:

        url = 'https://api.chaster.app/locks/658e78d24865e38abf4ecfed/history'
        headers = {
            'accept': 'application/json',
            'Authorization': f'Bearer {session["ca_access_token"]}',
            'Content-Type': 'application/json'
        }

        all_results = []  # Liste zum Speichern aller Ergebnisse
        lastId = None

        while True:
            data = {'limit': 100}
            if lastId:
                data['lastId'] = lastId

            try:
                response = requests.post(url, headers=headers, json=data)
                response.raise_for_status()
                response_data = response.json()

                current_results = response_data['results']
                all_results.extend(current_results)

                if not response_data['hasMore']:
                    break  # Schleife beenden, wenn keine weiteren Ergebnisse vorhanden sind

                lastId = current_results[-1]['_id']

            except requests.exceptions.RequestException as e:
                return {'success': False, 'error': str(e)}

        # Reihenfolge der gesammelten Ergebnisse umkehren
        all_results.reverse()

        # Verarbeitung der Ergebnisse
        for result in all_results:
            hist_id = result.get('_id')
            existing_entry = History_Chaster.query.filter_by(hist_id=hist_id).first()
            
            if not existing_entry:
                # Fügen Sie den Datensatz nur hinzu, wenn er noch nicht existiert
                new_history_entry = History_Chaster(
                        benutzer_id=current_user.id,
                        hist_id=hist_id,
                        lock_id=result.get('lock'),
                        type=result.get('type'),
                        created_at=result.get('createdAt'),
                        extension=result.get('extension'),
                        title=result.get('title'),
                        description=result.get('description'),
                        icon=result.get('icon')
                    )
                
                db.session.add(new_history_entry)

        # Commit der Änderungen an der Datenbank
        db.session.commit()

        return {'success': True}