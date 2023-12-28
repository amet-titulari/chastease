import requests
import os
from flask import Flask, redirect, request, render_template, url_for
from flask_login import LoginManager, login_user
from flask_migrate import Migrate
from dotenv import load_dotenv
from benutzer.models import db, Benutzer
from benutzer.user import benutzer

app = Flask(__name__)
load_dotenv()

app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('SQLALCHEMY_DATABASE_URI')
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY')
app.config['CA_CLIENT_ID'] = os.getenv('CA_CLIENT_ID')
app.config['CA_CLIENT_SECRET'] = os.getenv('CA_CLIENT_SECRET')
app.config['CA_BASE_ENDPOINT'] = os.getenv('CA_BASE_ENDPOINT')
app.config['CA_AUTHORIZATION_ENDPOINT'] = os.getenv('CA_AUTHORIZATION_ENDPOINT')
app.config['CA_TOKEN_ENDPOINT'] = os.getenv('CA_TOKEN_ENDPOINT')
app.config['CA_REDIRECT_URI'] = os.getenv('CA_REDIRECT_URI')



db.init_app(app)
migrate = Migrate(app, db)

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
    return render_template('index.html')

@app.route('/login')
def login():
    print(app.config['CA_REDIRECT_URI'])
    authorization_url = f"{app.config['CA_AUTHORIZATION_ENDPOINT']}?response_type=code&client_id={app.config['CA_CLIENT_ID']}&redirect_uri={app.config['CA_REDIRECT_URI']}"
    return redirect(authorization_url)

@app.route('/callback')
def callback():
    code = request.args.get('code')

    print("Erhaltener Code:", code)  # Loggen des Codes

    token_response = requests.post(
        app.config['CA_TOKEN_ENDPOINT'],
        data={
            'grant_type': 'authorization_code',
            'code': code,
            'redirect_uri': app.config['CA_REDIRECT_URI'],
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

    benutzer = Benutzer.query.filter_by(username=username).first()
    if not benutzer:
        benutzer = Benutzer(username=username, oauth2_token=access_token, oauth2_refresh_token=refresh_token)
        db.session.add(benutzer)
    else:
        benutzer.oauth2_token = access_token
        benutzer.oauth2_refresh_token = refresh_token

    db.session.commit()
    login_user(benutzer)

    return redirect(url_for('home'))

if __name__ == '__main__':
    app.run(debug=True)
