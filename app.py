
import os
import threading

from flask import Flask, redirect, request, render_template, url_for, session, flash
from flask_login import LoginManager, login_user, logout_user, current_user
from flask_migrate import Migrate, upgrade
from flask_sqlalchemy import SQLAlchemy
from flask_babel import Babel

from helper.log_config import logger

from dotenv import load_dotenv
from database import db

from api.chaster import handler_callback, get_auth_userinfo, get_hygiene_opening

from benutzer import benutzer
from extension import extension

from benutzer.models import Benutzer

from benutzer.routes import benutzer
from benutzer.token_handling import get_ttlock_tokens




load_dotenv()
app = Flask(__name__)

# Flask-Babel Konfiguration
babel = Babel(app)

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

# Flask-Babel Konfiguration
app.config['BABEL_DEFAULT_LOCALE'] = 'en'
app.config['BABEL_DEFAULT_TIMEZONE'] = 'Europe/Zurich'
app.config['BABEL_SUPPORTED_LANGUAGES'] = [ 'de', 'en']



db.init_app(app)
migrate = Migrate(app, db)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login' 
login_manager.login_message_category = 'info'

# Registrierung der Blueprints
app.register_blueprint(benutzer, url_prefix='/user')
app.register_blueprint(extension, url_prefix='/extension')


def get_locale():

    if 'language' in session:
        #print(f'Session Language : {session['language']}')
        return session['language']
    else:
        #print(f'Best Match : {request.accept_languages.best_match(app.config['BABEL_SUPPORTED_LANGUAGES'])}')
        return request.accept_languages.best_match(app.config['BABEL_SUPPORTED_LANGUAGES'])

babel.init_app(app, locale_selector=get_locale)


@login_manager.user_loader
def load_user(user_id):
    return Benutzer.query.get(int(user_id))

@app.route('/language/<language>')
def set_language(language):
    session['language'] = language
    session.modified = True
    #print(session['language'])
    return redirect(request.referrer or url_for('home'))

@app.route('/')
def home():
    if current_user.is_authenticated:
        result = get_hygiene_opening(current_user.CA_lock_id, session['ca_access_token'])
        #print(result)

        #from api.chaster import get_chaster_history
        #from api.ttlock import get_ttlock_history
        
        #thread1 = threading.Thread(target=get_chaster_history)
        #thread2 = threading.Thread(target=get_ttlock_history)

        #thread1.start()
        #thread2.start()


        if result['success']:
            content = f'<div class="container text-start">\
                    <h1>Hallo {current_user.username}</h1>\
                    <h3>Du kannst deine Hygeneöffnung jetzt durchführen</h3>\
                    <p>Viel Glück</p>\
                    </p>\
                    <a href="/user/relock" class="btn btn-info" role="button">Relock Session</a>\
                </div>'
        else:
        
            content = f'<div class="container text-start">\
                        <h1>Hallo {current_user.username}</h1>\
                        <h3>Sorry du bleibst verschlossen!</h3>\
                        <p>Viel Glück weiterhin!</p>\
                    </div>'




    else:

        content = f'    <div class="container text-start">\
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
            pass
    
        return redirect(url_for('home'))

@app.errorhandler(404)
def page_not_found(e):
    # Du kannst hier auch ein Template rendern statt eines einfachen Strings.
    return render_template('404.html') 



if __name__ == '__main__':
    if os.path.isfile('./instance/database.sqlite'):
        print("Die Datei existiert.")
    else:
        print("Die Datei existiert nicht.")
    app.run(debug=True)
