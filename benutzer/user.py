# benutzer/user.py
import json
import hashlib
from flask import Blueprint, current_app, render_template, request, flash
from flask_login import login_required, current_user
from .models import db, Benutzer, BenutzerConfig
from .forms import BenutzerConfigForm
from api.chaster import get_user_profile, get_user_lockid, get_user_lockinfo
from api.ttlock import get_ttlock_tokens

import os


benutzer = Blueprint('benutzer', __name__)


@benutzer.route('/config', methods=['GET', 'POST'])
@login_required
def config():
    user_config = BenutzerConfig.query.filter_by(benutzer_id=current_user.id).first()
    
    form = BenutzerConfigForm(obj=user_config)
    
    if form.validate_on_submit():
        if form.TTL_username:
            user_config.TTL_password_md5 = form.TTL_username

        if form.TTL_password_md5.data:
            # MD5-Hash des Passworts erzeugen
            hashed_password = hashlib.md5(form.TTL_password_md5.data.encode()).hexdigest()
            user_config.TTL_password_md5 = hashed_password
        
     

    if not user_config:
        user_config = BenutzerConfig(benutzer_id=current_user.id)
        db.session.add(user_config)
        flash('Benutzer angelegt!', 'success')
    else:
        flash('Benutzer besteht!', 'info')

    profile_data = get_user_profile(current_user.username, current_app.config['CA_CLIENT_ID'], current_app.config['CA_CLIENT_SECRET'])

    if profile_data:
        user_config.CA_user_id = profile_data.get('_id')
        user_config.CA_username = profile_data.get('username')

        # Zweiter API-Aufruf für Lock-Daten
        lock_data = get_user_lockid(user_config.CA_user_id, current_app.config['CA_CLIENT_ID'], current_app.config['CA_CLIENT_SECRET'])
        
        # Zugriff auf die gewünschten Daten
        user_config.CA_lock_id          = lock_data[0]['_id']
        user_config.CA_lock_status      = lock_data[0]['status']
        user_config.CA_lock_status      = lock_data[0]['combination']

        # Dritter API-Aufruf für Lock-Daten
        #print(user_config.__dict__)


        db.session.commit()
        flash('Konfiguration der Profildaten erstellt!', 'success')
    else:
        flash('Fehler beim Abrufen der Benutzerdaten (Profildaten)!', 'danger')

    lock_info = get_user_lockinfo(user_config.CA_lock_id, current_user.CA_access_token)
    #print(f'\n\n\n{lock_info}\n\n\n')

    if lock_info and 'keyholder' in lock_info:
        user_config.CA_keyholder_id = lock_info['keyholder']['_id']
        user_config.CA_keyholdername = lock_info['keyholder']['username']

        #print(user_config.CA_keyholdername,user_config.CA_keyholder_id)

        db.session.commit()
        flash('Keyholder Profil ermittelt!', 'success')
    else:
        flash('Keine Keyholderinformationen!', 'info')

    
    
    #print(user_config.__dict__)
   
    # bestehender Code für das Rendern des Templates
    return render_template('benutzerconfig.html', form=form)


