import requests
from flask import  request, session, render_template, jsonify, flash
from flask_login import login_user, current_user

from . import extension
from .forms import ExtensionConfigForm


from database import db
from benutzer.models import Benutzer


from benutzer.models import Benutzer

from api.cahaster_extension import get_session_auth_info, get_config_info

@extension.route('/')
def index():

    content = f'    <div class="container">\
                        <h1>Infos zur Erweiterungssession!</h1>\
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

                if not sessionauth.get('success'):
                    raise ValueError("Fehler bei der Authentifizierung.")

                user_data = sessionauth.get('data', {}).get('session', {}).get('lock', {}).get('user', {})
                if not user_data:
                    raise ValueError("Benutzerdaten nicht gefunden.")

                username = user_data.get('username')
                role = user_data.get('role')
                avatarUrl = user_data.get('avatarUrl')

                benutzer = Benutzer.query.filter_by(username=username).first()

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

                returnmsg = {
                                "success": True,
                                "message": "Token erfolgreich empfangen.",
                                "user"   : benutzer_info
                            }
                
                print(returnmsg)
                return jsonify(returnmsg),200



            except ValueError as e:
                return jsonify({"success": False, "message": str(e)}), 400  # Client-seitiger Fehler

            except Exception as e:
                return jsonify({"success": False, "message": "Ein unerwarteter Fehler ist aufgetreten."}), 500  # Server-seitiger Fehler

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
                print(f'Config_Info{configinfo}\n')
                
                sessiondata = configinfo['data']['session']
                print(f'Session Data: {sessiondata}\n')
                #print()
                configdata  = configinfo['data']['session']['config']
                print(f'Config Data: {configdata}\n')

                

            #print(f'Konigurationsinfo: {sessiondata}')
            print(f'\n\n')

            session_id              = sessiondata["sessionId"]
            lock_id                 = sessiondata["lock"]["_id"]
            lock_status             = sessiondata["lock"]["status"]
            combination_id          = sessiondata["lock"]["combination"]
            user_id                 = sessiondata["lock"]["user"]["_id"]
            username                = sessiondata["lock"]["user"]["username"]
            keyholder_id            = sessiondata["lock"]["keyholder"]["_id"]
            keyholdername           = sessiondata["lock"]["keyholder"]["username"]
            ttl_lock                = sessiondata["config"]["ttl_lock"]
            ttl_pass                = sessiondata["config"]["ttl_pass"]
            ttl_alias               = sessiondata["config"]["ttl_alias"]

            # Ausgabe der extrahierten Daten
            print("Session ID:", session_id)
            print("User ID:", user_id)
            print("Keyholder ID:", keyholder_id)
            print("Username:", username)
            print("Keyholdername:", keyholdername)
            print("Lock ID:", lock_id)
            print("Lock Status:", lock_status)
            print("Combination ID:", combination_id)
            print()
            print("Config TTL Lock:", ttl_lock)        
            print("Config TTL Pass:", ttl_pass)
            print("Config TTL Alias:", ttl_alias)


            returnmsg = {
                            "success": True,
                            "message": "Config Token OK.",
                            "data"   : sessiondata,
                            "config" : configdata
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
    pass