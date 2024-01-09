import requests
import os

from flask import Flask, redirect, request, render_template, url_for, session
from flask_login import LoginManager, login_user, logout_user
from flask_migrate import Migrate

from log_config import logger

from dotenv import load_dotenv
from datetime import datetime, timedelta
from benutzer.models import db, Benutzer
from benutzer.user import benutzer

from api.ttlock import get_ttlock_tokens

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
app.config['TTL_CLIENT_ID'] = os.getenv('TTL_CLIENT_ID')
app.config['TTL_CLIENT_SECRET'] = os.getenv('TTL_CLIENT_SECRET')


db.init_app(app)
migrate = Migrate(app, db)

CA_REDIRECT_URI = app.config['BASE_URL'] + 'callback'

login_manager = LoginManager()
login_manager.login_view = 'login'
login_manager.init_app(app)

# Registrierung des benutzer-Blueprints
app.register_blueprint(benutzer, url_prefix='/user')

@login_manager.user_loader
def load_user(user_id):
    return Benutzer.query.get(int(user_id))

@app.route('/')
def home():
    #logger.info('Homepage aufgerufen!')
    return render_template('index.html')

@app.route('/login')
def login():
    authorization_url = f"{app.config['CA_AUTHORIZATION_ENDPOINT']}?response_type=code&scope={app.config['CA_AUTHORIZATION_SCOPE']}&client_id={app.config['CA_CLIENT_ID']}&redirect_uri={CA_REDIRECT_URI}"
    return redirect(authorization_url)

@app.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('home'))

@app.route('/callback')
def callback():
    code = request.args.get('code')

    token_response = requests.post(
        app.config['CA_TOKEN_ENDPOINT'],
        data={
            'grant_type': 'authorization_code',
            'code': code,
            'redirect_uri': CA_REDIRECT_URI,
            'client_id': app.config['CA_CLIENT_ID'],
            'client_secret': app.config['CA_CLIENT_SECRET']
        }
    )
    token_data = token_response.json()
    access_token = token_data.get('access_token')
    refresh_token = token_data.get('refresh_token')

    user_info_url = f"{app.config['CA_BASE_ENDPOINT']}/auth/profile"
    user_info_response = requests.get(
        user_info_url, 
        headers={'Authorization': f'Bearer {access_token}'}
    )

    user_info = user_info_response.json()
    username = user_info.get('username')  # oder ein anderes relevantes Feld
    role = user_info.get('role')  # oder ein anderes relevantes Feld

    # Tokens in der Session statt in der Datenbank speichern
    session['ca_access_token'] = access_token
    session['ca_refresh_token'] = refresh_token
    session['ca_token_expiration_time'] = datetime.now() + timedelta(seconds=token_data['expires_in'])

    benutzer = Benutzer.query.filter_by(username=username).first()
    if not benutzer:
        benutzer = Benutzer(username=username, role=role)
        db.session.add(benutzer)
        return redirect(url_for('benutzer.config'))
    


    db.session.commit()
    login_user(benutzer)

    if benutzer.TTL_username and benutzer.TTL_password_md5:
        TT_lock_tokens = get_ttlock_tokens(app.config['TTL_CLIENT_ID'], 
                                           app.config['TTL_CLIENT_SECRET'], 
                                           benutzer.TTL_username, 
                                           benutzer.TTL_password_md5)
        
        if TT_lock_tokens['success']:
            # Erfolgsfall: Verarbeiten Sie die zurückgegebenen Daten
            
            session['ttl_access_token'] = token_data.get('access_token')
            session['ttl_refresh_token'] = refresh_token
            session['ttl_token_expiration_time'] = datetime.now() + timedelta(seconds=token_data['expires_in'])

            print(f'Chaster Token Expiration: {session["ca_token_expiration_time"]}, TTL Token Expiration: {session["ttl_token_expiration_time"]}')



    return redirect(url_for('home'))

if __name__ == '__main__':
    app.run(debug=True)
