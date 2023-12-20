# benutzer/user.py
from flask import Blueprint, render_template, redirect, url_for, request, flash
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import login_user, logout_user, login_required, current_user
from .models import db, Benutzer, BenutzerConfig
from .forms import BenutzerConfigForm

import os
import api.ttlock
import api.chaster

auth = Blueprint('auth', __name__)

@auth.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        user = Benutzer.query.filter_by(username=username).first()

        if user and check_password_hash(user.password, password):
            login_user(user)
            return redirect(url_for('home'))  # Angenommen, es gibt eine 'index'-Route in Ihrer Hauptanwendung
        else:
            flash('Login fehlgeschlagen. Bitte überprüfen Sie Ihre Anmeldedaten.','danger')

    return render_template('login.html')

@auth.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        password2 = request.form.get('password2')

        user = Benutzer.query.filter_by(username=username).first()

        if user:
            flash('Benutzername existiert bereits.','danger')
        elif password != password2:
            flash('Passwörter stimmen nicht überein.','danger')
        else:
            # Hier wird das Passwort gehasht
            hashed_password = generate_password_hash(password, method='pbkdf2:sha256')
            new_user = Benutzer(username=username, password=hashed_password)
            db.session.add(new_user)
            db.session.commit()

            return redirect(url_for('auth.login'))

    return render_template('signup.html')

@auth.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('home'))  # Rückkehr zur Hauptseite

@auth.route('/config', methods=['GET', 'POST'])
@login_required
def config():
    # Vorhandene Konfiguration abrufen
    user_config = BenutzerConfig.query.filter_by(benutzer_id=current_user.id).first()

    if user_config:
        form = BenutzerConfigForm(obj=user_config)
    else:
        form = BenutzerConfigForm()

    if form.validate_on_submit():
        if user_config:
            form.populate_obj(user_config)
        else:
            user_config = BenutzerConfig(benutzer_id=current_user.id)
            form.populate_obj(user_config)
            db.session.add(user_config)

        db.session.commit()

        # Chaster API Aufruf zum erhalt der User_ID:
        if user_config.CA_username:
            CA_client_id = os.environ.get('CA_CLIENT_ID')
            CA_client_secret = os.environ.get('CA_CLIENT_SECRET')

            # API-Aufruf für Chaster
            profile_data = api.chaster.get_user_profile(user_config.CA_username, CA_client_id, CA_client_secret)


            if profile_data and '_id' in profile_data:
                user_config.CA_user_id = profile_data['_id']
                db.session.commit()

        else:
            user_config.CA_user_id = ''
            db.session.commit()
        
        

        db.session.commit()

        # Prüfen, ob Benutzername und Passwort vorhanden sind
        if user_config.TTL_username and user_config.TTL_password_md5:
            TTL_client_ID = os.environ.get('TTL_CLIENT_ID')
            TTL_client_secret = os.environ.get('TTL_CLIENT_SECRET')
            tokens = api.ttlock.get_ttlock_tokens(TTL_client_ID, TTL_client_secret, user_config.TTL_username, user_config.TTL_password_md5)

            if 'access_token' in tokens:
                user_config.TTL_access_token = tokens['access_token']
                user_config.TTL_refresh_token = tokens['refresh_token']
                db.session.commit()
                flash('Konfiguration aktualisiert!', 'success')
            else:
                flash('Fehler beim Abrufen der Tokens', 'danger')
        else:
            user_config.TTL_access_token = ''
            user_config.TTL_refresh_token = ''
            db.session.commit()
            flash('TTL-Benutzername oder Passwort fehlen', 'danger')

        return redirect(url_for('auth.config'))

    return render_template('benutzerconfig.html', form=form)
