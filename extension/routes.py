import requests
from flask import  request, session, render_template, jsonify, flash
from flask_login import login_user, current_user

from . import extension
from .forms import ExtensionConfigForm


from database import db
from benutzer.models import Benutzer


from benutzer.models import Benutzer

from api.cahaster_extension import get_session_auth_info, get_config_info, put_config_update

@extension.route('/')
def index():

    content = f'    <div class="container">\
                        <h1>Erweiterungssession!</h1>\
                        <h3></h3>\
                        <p></p>\
                    </div>'

    #return redirect(url_for('extension.handle_token'))
    return render_template('extension/index.html', content=content) 

@extension.route('/handle_token', methods=['GET', 'POST'])
def handle_token():
    if request.method == 'POST':
            try:
                data = request.json
                main_token = data.get('mainToken')

                if not main_token:
                    raise ValueError("Kein Token gefunden.")

                session['main_token'] = main_token
                sessionauth = get_session_auth_info(main_token)
                #print(f'\nSessionauth: {sessionauth}\n')

                if not sessionauth.get('success'):
                    raise ValueError("Fehler bei der Authentifizierung.")

                user_data = sessionauth.get('data', {}).get('session', {}).get('lock', {}).get('user', {})
                if not user_data:
                    raise ValueError("Benutzerdaten nicht gefunden.")

                username = user_data.get('username')
                role = user_data.get('role')
                avatarUrl = user_data.get('avatarUrl')

                #print(f'\nUserinfo: {username}\t{role}\t{avatarUrl}\n')

                benutzer = Benutzer.query.filter_by(username=username).first()
                #print(f'\nBenutzer: {benutzer}')

                if not benutzer:
                    benutzer = Benutzer(username=username, role=role, avatarUrl=avatarUrl)
                    db.session.add(benutzer)
                    db.session.commit()
                    login_user(benutzer)
                else:
                    benutzer.role = role
                    benutzer.avatarUrl = avatarUrl
                    login_user(benutzer)

                # Zusätzliche Logik nach dem Login
                # Zum Beispiel: Session-Infos abrufen, weitere Daten verarbeiten usw.
                    
                benutzer_info = benutzer.to_dict()

                #print(f'\nBenutzer Info: {benutzer_info}')

                returnmsg = {
                                "success": True,
                                "message": "Token erfolgreich empfangen.",
                                "user"   : benutzer_info
                            }
                
                #print(returnmsg)
                return jsonify(returnmsg),200



            except ValueError as e:
                return jsonify({"success": False, "message": str(e)}), 400  # Client-seitiger Fehler

            except Exception as e:
                return jsonify({"success": False, "message": str(e)}), 500  # Server-seitiger Fehler

    elif request.method == 'GET':
        print("Methode GET")
        # Hier können Sie entscheiden, was bei einem GET-Request passieren soll.
        # Zum Beispiel: Eine bestimmte Information als JSON zurückgeben oder eine einfache Nachricht.
        return jsonify({"message": "GET-Request ist für diese Route nicht zulässig."}), 405

@extension.route('/config', methods=['GET', 'POST'])
def config():

    form = ExtensionConfigForm()
    if form.validate_on_submit():
        # Hier könnten Sie die Daten verarbeiten, z.B. in einer Datenbank speichern
        flash('Formular erfolgreich eingereicht!')
    
    content = f'    <div class="container">\
                        <h1>Konfiguration!</h1>\
                        <h3></h3>\
                        <p></p>\
                    </div>'

    #return redirect(url_for('extension.handle_token'))
    return render_template('extension/config.html', content=content, form=form) 

@extension.route('/configupdate/<token>', methods=['PUT'])
def configupdate(token):
    print(f'Konigupdate gestartet: {token}')
    if request.method == 'PUT':
        print(f'PUT ist gestartet')
        try:
            data = request.json
            #print(f'Konfiguration: {data}')
          
            update = put_config_update(token,data)
            print(update)

            returnmsg = {
                            "success": True,
                            "message": "Update Running",
                            "data"   : "DATA"
                        }
            
            
            return jsonify(returnmsg),200



        except ValueError as e:
            return jsonify({"success": False, "message": str(e)}), 400  # Client-seitiger Fehler


    elif request.method == 'GET':
        print("Methode GET")
        # Hier können Sie entscheiden, was bei einem GET-Request passieren soll.
        # Zum Beispiel: Eine bestimmte Information als JSON zurückgeben oder eine einfache Nachricht.
        return jsonify({"message": "GET-Request ist für diese Route nicht zulässig."}), 405

@extension.route('/fetchconfig', methods=['GET', 'POST'])
def fetchconfig():
    
    if request.method == 'POST':
        try:
            data = request.json
            configurationToken = data.get('configurationToken')

            if not configurationToken:
                raise ValueError("Kein Token gefunden.")
            
            configinfo = get_config_info(configurationToken)
            if configinfo['success']:
                #print(f'Config_Info{configinfo}\n')
                sessiondata = configinfo['data']['session']
                print(f'Session Data: {sessiondata}\n')
                #print()
                configdata  = configinfo['data']['session']['config']
                #print(f'Config Data: {configdata}\n')


            returnmsg = {
                            "success": True,
                            "message": "Config Token OK.",
                            "data"   : configdata
                        }
            
            
            return jsonify(returnmsg),200



        except ValueError as e:
            return jsonify({"success": False, "message": str(e)}), 400  # Client-seitiger Fehler


    elif request.method == 'GET':
        print("Methode GET")
        # Hier können Sie entscheiden, was bei einem GET-Request passieren soll.
        # Zum Beispiel: Eine bestimmte Information als JSON zurückgeben oder eine einfache Nachricht.
        return jsonify({"message": "GET-Request ist für diese Route nicht zulässig."}), 405

@extension.route('/hooks', methods=['POST'])
def hooks():
    # Prüfen, ob es sich um eine JSON-Anfrage handelt
    if request.is_json:
        # Anfragedaten extrahieren
        data = request.get_json()
        print("Erhaltene Daten:", data)

        # Hier können Sie basierend auf den Daten Verarbeitungslogik hinzufügen.
        # Zum Beispiel:
        # if data['event_type'] == 'extension_session.created':
        #     # Logik für die Behandlung des Ereignisses extension_session.created

        # Bestätigung des Empfangs senden
        return jsonify({"message": "Ereignis erfolgreich empfangen!"}), 200
    else:
        return jsonify({"error": "Anfrage muss JSON sein"}), 400
