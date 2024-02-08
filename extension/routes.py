from flask import  request, session, render_template, redirect, url_for, flash
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

            except ValueError as e:
                flash(str(e))
                return redirect(url_for('login_page'))  # Ändern Sie dies entsprechend
            except Exception as e:
                flash("Ein unerwarteter Fehler ist aufgetreten: " + str(e))
                return redirect(url_for('error_page'))  # Ändern Sie dies entsprechend

    elif request.method == 'GET':
            print("Methode GET")

        # Weiterleitung oder Anzeige einer Seite nach erfolgreicher Anmeldung
    print("user: ", current_user)
    return render_template('extension/home.html') 
  

@extension.route('/config', methods=['POST'])
def config():
    pass


@extension.route('/hooks', methods=['POST'])
def hooks():
    pass