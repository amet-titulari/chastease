
import os
import redis

from flask import Flask, redirect, request, render_template, url_for, session, flash
from flask_login import LoginManager, login_user, logout_user, current_user
from flask_migrate import Migrate, upgrade
from flask_sqlalchemy import SQLAlchemy

from helper.log_config import logger

from dotenv import load_dotenv
from database import db

from api.chaster import handler_callback, get_auth_userinfo

from benutzer import benutzer
from extension import extension

from benutzer.models import Benutzer, LockHistory, Journal
from extension.models import Session


from benutzer.routes import benutzer
from benutzer.token_handling import get_ttlock_tokens


app = Flask(__name__)
# Weitere Konfigurationen und Initialisierungen...



from api.chaster import get_lock_history



load_dotenv()
app = Flask(__name__)

app.config['BASE_URL'] = os.getenv('BASE_URL')
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('SQLALCHEMY_DATABASE_URI')
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY')
app.config['LOG_LEVEL'] = os.getenv('LOG_LEVEL')

app.config['CA_CLIENT_ID'] = os.getenv('CA_CLIENT_ID')
app.config['CA_CLIENT_SECRET'] = os.getenv('CA_CLIENT_SECRET')
app.config['CA_BASE_ENDPOINT'] = os.getenv('CA_BASE_ENDPOINT')
app.config['CA_AUTHORIZATION_SCOPE'] = os.getenv('CA_AUTHORIZATION_SCOPE')
app.config['CA_AUTHORIZATION_ENDPOINT'] = os.getenv('CA_AUTHORIZATION_ENDPOINT')
app.config['CA_TOKEN_ENDPOINT'] = os.getenv('CA_TOKEN_ENDPOINT')
app.config['CA_DEV_TOKEN'] = os.getenv('CA_DEV_TOKEN')

app.config['TTL_CLIENT_ID'] = os.getenv('TTL_CLIENT_ID')
app.config['TTL_CLIENT_SECRET'] = os.getenv('TTL_CLIENT_SECRET')


# Initialisierung von Erweiterungen
# Pfad zur Datei, die Sie überprüfen möchten




db.init_app(app)
migrate = Migrate(app, db)
login_manager = LoginManager()
login_manager.init_app(app)

# Registrierung der Blueprints
app.register_blueprint(benutzer, url_prefix='/user')
app.register_blueprint(extension, url_prefix='/extension')


@login_manager.user_loader
def load_user(user_id):
    return Benutzer.query.get(int(user_id))

@app.route('/')
def home():
    if current_user.is_authenticated:
        history = get_lock_history()
        if not history['success']:
            flash(f'Fehler beim Abrufen der Lock-History', 'danger')

    content = f'    <div class="container">\
                        <h1>Willkommen bei Chastease!</h1>\
                        <h3>Diese Anwendung ist zur automatischen Steuerung des Schlüsseltresors mit TTLock.</h3>\
                        <p>Bitte melde dich an deinem Chaster Account an und erteile die notwendigen Berechtigungen.</p>\
                    </div>'

    return render_template('index.html', content=content) 

@app.route('/login')
def login():
    authorization_url = f"{app.config['CA_AUTHORIZATION_ENDPOINT']}?response_type=code&scope={app.config['CA_AUTHORIZATION_SCOPE']}&client_id={app.config['CA_CLIENT_ID']}&redirect_uri={app.config['BASE_URL'] + 'callback'}"
    return redirect(authorization_url)

@app.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('home'))

@app.route('/callback')
def callback():
    code = request.args.get('code')

    res_handler_calback = handler_callback(code)
    if res_handler_calback['success']:
        res_auth_info = get_auth_userinfo()
        print(res_auth_info)
        if not res_auth_info['success']:
            flash(f'Benutzeranmeldung fehlgeschlagen','danger')
    else:
        flash(f'Error: Callback Handler!')

    benutzer = Benutzer.query.filter_by(username=session['username']).first()
    if not benutzer.TTL_username or not benutzer.TTL_password_md5:
        flash('Benutzername oder Passwort für TTLock fehlt. Bitte aktualisieren Sie Ihre Konfiguration.', 'warning')
        return redirect(url_for('benutzer.config'))
    else:

        TT_lock_tokens = get_ttlock_tokens()
        print(TT_lock_tokens)

        if 'errcode' in TT_lock_tokens:
                error_message = TT_lock_tokens.get('errmsg', 'Ein unbekannter Fehler ist aufgetreten.')
                flash(f'TTLock Config: {error_message}', 'danger') 
                return redirect(url_for('benutzer.config')) 
        
        if TT_lock_tokens['success']:
            # Erfolgsfall: Verarbeiten Sie die zurückgegebenen Daten
            pass

    print(benutzer) 
    # Verbindung zur Redis-Datenbank herstellen
    redis_client = redis.StrictRedis(host='localhost', port=6379, db=0)

    # Beispiel: Benutzerdaten in Redis speichern
    username = session['username']
    user_data = {
        
            "username": benutzer.username,
            "id": benutzer.id,
            "lock_uuid": benutzer.lock_uuid,
            "role": benutzer.role,
            "avatarUrl": benutzer.avatarUrl,
            "CA_user_id": benutzer.CA_user_id,
            "CA_username": benutzer.CA_username,
            "CA_lock_id": benutzer.CA_lock_id,
            "CA_lock_status": benutzer.CA_lock_status,
            "CA_keyholder_id": benutzer.CA_keyholder_id,
            "CA_keyholdername": benutzer.CA_keyholdername,
            "CA_combination_id": benutzer.CA_combination_id,
            "TTL_username": benutzer.TTL_username,
            "TTL_password_md5": benutzer.TTL_password_md5,
            "TTL_lock_alias": benutzer.TTL_lock_alias,
            "TTL_lock_id": benutzer.TTL_lock_id,
        
    }

    # None-Werte in leere Strings umwandeln
    for key, value in user_data.items():
        if value is None:
            user_data[key] = ''

    # Die Benutzerdaten in Redis speichern
    redis_client.hmset(username, user_data)           

                

    return redirect(url_for('home'))

if __name__ == '__main__':
    if os.path.isfile('./instance/database.sqlite'):
        print("Die Datei existiert.")
    else:
        print("Die Datei existiert nicht.")
    app.run(debug=True)
