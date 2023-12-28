# benutzer/user.py
from flask import Blueprint, render_template, redirect, url_for, request, flash
from flask_login import login_required, current_user
from .models import db, Benutzer, BenutzerConfig
from .forms import BenutzerConfigForm
from api.chaster import get_user_profile, get_user_lockid
from api.ttlock import get_ttlock_tokens

import os


benutzer = Blueprint('benutzer', __name__)


@benutzer.route('/config', methods=['GET', 'POST'])
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
            profile_data = get_user_profile(user_config.CA_username, CA_client_id, CA_client_secret)


            if profile_data and '_id' in profile_data:
                user_config.CA_user_id = profile_data['_id']
                db.session.commit()
                flash('Konfiguration aktualisiert!', 'success')

            else:
                user_config.CA_user_id = ''
                user_config.CA_lock_id = ''
                db.session.commit()
                flash('Fehler bei Benutzerprüfung!', 'danger')
        
        # Chaster API Aufruf zum erhalt der LOCK_ID:
        if user_config.CA_user_id:
            CA_client_id = os.environ.get('CA_CLIENT_ID')
            CA_client_secret = os.environ.get('CA_CLIENT_SECRET')

            # API-Aufruf für Chaster
            lock_data = get_user_lockid(user_config.CA_user_id, CA_client_id, CA_client_secret)



            if lock_data and '_id' in lock_data[0]:
                user_config.CA_lock_id = lock_data[0]['_id']
                db.session.commit()
                flash('Konfiguration aktualisiert!', 'success')
            else:
                user_config.CA_lock_id = ''
                db.session.commit()
                flash('Konfiguration nicht aktualisiert! Es ist kein Lock vorhanden!', 'danger')

        

        db.session.commit()

        # Prüfen, ob Benutzername und Passwort vorhanden sind
        if user_config.TTL_username and user_config.TTL_password_md5:
            TTL_client_ID = os.environ.get('TTL_CLIENT_ID')
            TTL_client_secret = os.environ.get('TTL_CLIENT_SECRET')
            tokens = get_ttlock_tokens(TTL_client_ID, TTL_client_secret, user_config.TTL_username, user_config.TTL_password_md5)

            if 'access_token' in tokens:
                user_config.TTL_access_token = tokens['access_token']
                user_config.TTL_refresh_token = tokens['refresh_token']
                db.session.commit()
                flash('Konfiguration aktualisiert!', 'success')
            else:
                user_config.TTL_access_token = ''
                user_config.TTL_refresh_token = ''
                db.session.commit()
                flash('Fehler beim Abrufen der Tokens', 'danger')
        else:
            user_config.TTL_access_token = ''
            user_config.TTL_refresh_token = ''
            db.session.commit()
            
        return redirect(url_for('benutzer.config'))

    return render_template('benutzerconfig.html', form=form)
