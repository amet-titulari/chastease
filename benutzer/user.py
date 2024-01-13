# benutzer/user.py

import re
import hashlib

from flask import Blueprint, current_app, session, redirect, request, flash, url_for,render_template
from flask_login import login_required, current_user

from helper.log_config import logger

from .models import db, Benutzer, CA_Lock_History
from .forms import BenutzerConfigForm
from .qrcode import generate_qr
from .token_handling import is_ca_token_valid, is_ttl_token_valid

from api.chaster import *

from api.ttlock import get_lock_list, open_ttlock
from benutzer.token_handling import get_ttlock_tokens

benutzer = Blueprint('benutzer', __name__)

def is_md5(s):
    return bool(re.match(r'^[a-fA-F0-9]{32}$', s))

@benutzer.route('/config', methods=['GET', 'POST'])
@login_required
def config():
    benutzer = Benutzer.query.filter_by(id=current_user.id).first()
    form = BenutzerConfigForm(obj=benutzer)

    if request.method == 'POST' and form.validate_on_submit():
        # Formularverarbeitung für POST-Anfrage
        benutzer.TTL_username = form.TTL_username.data or benutzer.TTL_username

        if form.TTL_password_md5.data:
            benutzer.TTL_password_md5 = (hashlib.md5(form.TTL_password_md5.data.encode()).hexdigest() 
                                         if not is_md5(form.TTL_password_md5.data) 
                                         else form.TTL_password_md5.data)

        benutzer.TTL_lock_alias = form.TTL_lock_alias.data or benutzer.TTL_lock_alias

        db.session.commit()
        flash('Konfiguration aktualisiert!', 'success')

    # GET-Anfrage oder POST-Anfrage mit ungültigem Formular
    # Laden Sie hier die Profil-, Lock- und TTLock-Informationen
    profile_data = get_user_profile(current_user.username, current_app.config['CA_CLIENT_ID'], current_app.config['CA_CLIENT_SECRET'])

    if profile_data['success']:
        benutzer.CA_user_id = profile_data['data'].get('_id')
        benutzer.CA_username = profile_data['data'].get('username')
        db.session.commit()
    else:
        flash(f'Fehler beim Abrufen des Benutzerprofils: {profile_data["error"]}', 'danger')

    lock_data = get_user_lockid(benutzer.CA_user_id, current_app.config['CA_CLIENT_ID'], current_app.config['CA_CLIENT_SECRET'])

    if lock_data['success']:
        if lock_data['data']:
            benutzer.CA_lock_id = lock_data['data'][0].get('_id')
            benutzer.CA_lock_status = lock_data['data'][0].get('status')
            benutzer.CA_lock_combination = lock_data['data'][0].get('combination')
            db.session.commit()
        else:
            flash('Die Antwort enthält keine Lock-Daten.', 'warning')
    else:
        flash(f'Fehler beim Abrufen der Lock-Daten: {lock_data["error"]}', 'danger')

    lock_info = get_user_lockinfo(benutzer.CA_lock_id, session['ca_access_token'])

    if lock_info['success']:
        if 'keyholder' in lock_info['data']:
            benutzer.CA_keyholder_id = lock_info['data']['keyholder']['_id']
            benutzer.CA_keyholdername = lock_info['data']['keyholder']['username']
            db.session.commit()
        else:
            flash('Keine Keyholderinformationen vorhanden.', 'info')
    else:
        flash(f'Fehler beim Abrufen der Lock-Informationen: {lock_info["error"]}', 'danger')

    # TT Lockinfo
    if benutzer.TTL_username and benutzer.TTL_password_md5:
        gettoken = get_ttlock_tokens()
        
        if not gettoken.get('success'):
            benutzer.TTL_username = None
            benutzer.TTL_password_md5 = None
            benutzer.TTL_lock_alias = None
        else:
            TT_lock_list = get_lock_list(current_app.config['TTL_CLIENT_ID'], session['ttl_access_token'])

            lock_id = None

            if benutzer.TTL_lock_alias:
                for item in TT_lock_list['data']['list']:
                    if item.get('lockAlias') == benutzer.TTL_lock_alias:
                        lock_id = item.get('lockId')
                        lock_alias = benutzer.TTL_lock_alias
            else:
                lock_id = TT_lock_list["data"]["list"][0]['lockId']
                lock_alias = TT_lock_list["data"]["list"][0]['lockAlias']
                flash(f'Das erstge TTLock mit dem Alias {lock_alias} wurde ausgewählt!','warning')

            if lock_id is not None:
                benutzer.TTL_lock_id = lock_id
                benutzer.TTL_lock_alias = lock_alias

            db.session.commit()
        
    # Formulardaten aktualisieren
    form = BenutzerConfigForm(obj=benutzer)
    return render_template('benutzerconfig.html', form=form)

@benutzer.route('/relock')
@login_required
def relock():

    benutzer = Benutzer.query.filter_by(id=current_user.id).first()


    qrcode = generate_qr()
    if qrcode['success']:

        benutzer.lock_uuid = qrcode['qr_uuid']
        db.session.commit()

        lock_info = get_user_lockinfo(benutzer.CA_lock_id, session['ca_access_token'])

        if lock_info['success']:
            # Zugriff auf das 'data'-Feld
            data = lock_info['data']

            # Zugriff auf das 'extensions'-Feld innerhalb von 'data'
            extensions = data.get('extensions', [])

            # Durchsuchen der Extensions
            for extension in extensions:
                if extension.get("slug") == "temporary-opening":
                    # Zugriff auf das 'userData'-Feld
                    user_data = extension.get("userData", {})
                    # Auslesen des 'openedAt'-Wertes
                    opened_at = user_data.get("openedAt")
                    if opened_at is not None:
                        filepath = f'qrcodes/{benutzer.lock_uuid}.png'

                        lockupload = upload_lock_image(session['ca_access_token'],filepath )
                        if lockupload['success']:  
                            combination_id = lockupload['data']['combinationId']
                            
                            udt = update_combination_relock(benutzer.CA_lock_id, session['ca_access_token'], combination_id)
                            if udt['success']:
                                flash(f'Dein Chaster-Lock ist wieder verschlossen', 'success')
                        else:
                            flash('Upload nicht ok!', 'success')



                        return redirect(url_for('home'))
                    else:
                        flash(f'Dein Chaster-Lock ist VERSCHLOSSEN', 'danger')
                        return redirect(url_for('home'))
            else:
                print("Keine Extension mit dem Slug 'temporary-opening' gefunden.")
        else:
            print("Die Antwort war nicht erfolgreich.")


@benutzer.route('/ttl_open/<uid>')
@login_required
def ttl_open(uid):

    benutzer = Benutzer.query.filter_by(id=current_user.id).first()


    if benutzer.lock_uuid == uid:
        
            open_ttlock()
            flash(f'Die UID {uid} ist korrekt und öffnet das TTLock!', 'success')

            #Nach Gebrauch UUID löschen um eine zweite Öffnung zu verhindern
            #benutzer.lock_uuid = ''
            #db.session.commit()

    else:
            flash(f'Die UID {uid} ist nicht korrekt das TTLock bleibt verschlossen!', 'danger')
        
    return redirect(url_for('home'))

@benutzer.route('/history')
@login_required
def get_ca_lockhistory():

        history = get_lock_history()

        if history['success']:
            flash('Hat prima geklappt', 'info')
        else:
            flash(f'Fehler beim Abrufen der Lock-History', 'danger')

        return render_template('index.html')
