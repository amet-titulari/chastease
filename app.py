
import os
import time

from flask import Flask, redirect, request, render_template, url_for, session, flash
from flask_login import LoginManager, login_user, logout_user, current_user
from flask_migrate import Migrate

from helper.log_config import logger

from dotenv import load_dotenv

from database import db

from api.chaster import handler_callback, get_auth_userinfo

from benutzer import benutzer
from benutzer.models import Benutzer
from benutzer.routes import benutzer
from benutzer.token_handling import get_ttlock_tokens

from ca_extension import ca_extension

app = Flask(__name__)
# Weitere Konfigurationen und Initialisierungen...



from api.chaster import get_lock_history


app = Flask(__name__)

load_dotenv()

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


db.init_app(app)
migrate = Migrate(app, db)

login_manager = LoginManager()
login_manager.login_view = 'login'
login_manager.init_app(app)

# Registrierung der Blueprints
app.register_blueprint(benutzer, url_prefix='/user')
app.register_blueprint(ca_extension, url_prefix='/extension')

@login_manager.user_loader
def load_user(user_id):
    return Benutzer.query.get(int(user_id))

@app.route('/')
def home():
    if current_user.is_authenticated:
        history = get_lock_history()
        if not history['success']:
            flash(f'Fehler beim Abrufen der Lock-History', 'danger')
    return render_template('index.html') 

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

        if 'errcode' in TT_lock_tokens:
                error_message = TT_lock_tokens.get('errmsg', 'Ein unbekannter Fehler ist aufgetreten.')
                flash(f'TTLock Config: {error_message}', 'danger') 
                return redirect(url_for('benutzer.config')) 
        
        if TT_lock_tokens['success']:
            # Erfolgsfall: Verarbeiten Sie die zurückgegebenen Daten
            
            session['ttl_access_token'] = TT_lock_tokens.get('access_token')
            session['ttl_refresh_token'] = TT_lock_tokens.get('refresh_token')
            session['ttl_token_expiration_time'] = time.time() + TT_lock_tokens['expires_in']
                

    return redirect(url_for('home'))

if __name__ == '__main__':
    app.run(debug=True)
