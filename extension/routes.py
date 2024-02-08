from flask import  request, session, render_template, jsonify, flash
from flask_login import login_user, current_user

from . import extension

from database import db
from benutzer.models import Benutzer


from benutzer.models import Benutzer

from api.cahaster_extension import get_session_auth_info, get_session_info

@extension.route('/')
def index():

    print(current_user.is_authenticated)

    content = f'    <div class="container">\
                        <h1>Infos zur Erweiterungssession!</h1>\
                        <h3></h3>\
                        <p></p>\
                    </div>'

    #return redirect(url_for('extension.handle_token'))
    return render_template('extension/index.html', content=content) 

@extension.route('/home')
def home():

    print(current_user.is_authenticated)


    return render_template('extension/home.html') 
 


@extension.route('/handle_token', methods=['GET', 'POST'])
def handle_token():
    print("Methode : ", request.method)

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
                    
                
                returnmsg = {
                                "success": True,
                                "message": "Token erfolgreich empfangen."
                            }
                
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

  

@extension.route('/config', methods=['POST'])
def config():
    pass


@extension.route('/hooks', methods=['POST'])
def hooks():
    pass