# benutzer/user.py

import re
import hashlib
from flask import Blueprint, current_app, session, redirect, request, flash, url_for,render_template
from flask_login import login_required, current_user
from .models import db, Benutzer
from .forms import BenutzerConfigForm
from .qrcode import generate_qr
from api.chaster import get_user_profile, get_user_lockid, get_user_lockinfo, upload_lock_image, update_combination_relock
from api.ttlock import get_ttlock_tokens,get_lock_list,get_lock_detail, open_ttlock

import os


benutzer = Blueprint('benutzer', __name__)

def is_md5(s):
    return bool(re.match(r'^[a-fA-F0-9]{32}$', s))


@benutzer.route('/config', methods=['GET', 'POST'])
@login_required
def config():
    benutzer = Benutzer.query.filter_by(id=current_user.id).first()
    form = BenutzerConfigForm(obj=benutzer)

    if request.method == 'POST' and form.validate_on_submit():
        
        if form.validate_on_submit():

            if form.TTL_lock_alias.data:
                benutzer.TTL_lock_alias = form.TTL_lock_alias.data

            if form.TTL_username.data:
                benutzer.TTL_username = form.TTL_username.data

            if form.TTL_password_md5.data:
                if not is_md5(form.TTL_password_md5.data):
                    # MD5-Hash des Passworts erzeugen, wenn es kein MD5-Hash ist
                    hashed_password = hashlib.md5(form.TTL_password_md5.data.encode()).hexdigest()
                    benutzer.TTL_password_md5 = hashed_password
                else:
                    # Direkt zuweisen, wenn es bereits ein MD5-Hash ist
                    benutzer.TTL_password_md5 = form.TTL_password_md5.data

        db.session.commit()
        flash('Konfiguration aktualisiert!', 'success')
        return redirect(url_for('benutzer.config'))


    profile_data = get_user_profile(current_user.username, current_app.config['CA_CLIENT_ID'], current_app.config['CA_CLIENT_SECRET'])

    if profile_data['success']:
        # Erfolgsfall: Verarbeiten Sie die zurückgegebenen Daten
        benutzer.CA_user_id = profile_data['data'].get('_id')
        benutzer.CA_username = profile_data['data'].get('username')
        db.session.commit()
    else:
        # Fehlerfall: Zeigen Sie eine Fehlermeldung an
        flash(f'Fehler beim Abrufen des Benutzerprofils: {profile_data["error"]}', 'danger')


    # Zweiter API-Aufruf für Lock-Daten 
    lock_data = get_user_lockid(benutzer.CA_user_id, current_app.config['CA_CLIENT_ID'], current_app.config['CA_CLIENT_SECRET'])

    if lock_data['success']:
        # Erfolgsfall: Verarbeiten Sie die zurückgegebenen Daten
        # Stellen Sie sicher, dass die Antwort die erwarteten Daten enthält
        if lock_data['data']:
            benutzer.CA_lock_id = lock_data['data'][0].get('_id')
            benutzer.CA_lock_status = lock_data['data'][0].get('status')
            benutzer.CA_lock_combination = lock_data['data'][0].get('combination')

            db.session.commit()
        else:
            # Falls die Antwort leer ist oder die erwarteten Daten nicht enthält
            flash('Die Antwort enthält keine Lock-Daten.', 'warning')
    else:
        # Fehlerfall: Zeigen Sie eine Fehlermeldung an
        flash(f'Fehler beim Abrufen der Lock-Daten: {lock_data["error"]}', 'danger')

    lock_info = get_user_lockinfo(benutzer.CA_lock_id, session['access_token'])

    if lock_info['success']:
        # Überprüfen, ob die Antwort die notwendigen 'keyholder' Informationen enthält
        if 'keyholder' in lock_info['data']:
            benutzer.CA_keyholder_id = lock_info['data']['keyholder']['_id']
            benutzer.CA_keyholdername = lock_info['data']['keyholder']['username']

            db.session.commit()
        else:
            # Falls die 'keyholder' Informationen nicht in der Antwort vorhanden sind
            flash('Keine Keyholderinformationen vorhanden.', 'info')
    else:
        # Fehlerfall: Zeigen Sie eine Fehlermeldung an
        flash(f'Fehler beim Abrufen der Lock-Informationen: {lock_info["error"]}', 'danger')


    # TT Lockinfo
    if benutzer.TTL_username and benutzer.TTL_password_md5:
        TT_lock_tokens = get_ttlock_tokens(current_app.config['TTL_CLIENT_ID'], 
                                        current_app.config['TTL_CLIENT_SECRET'], 
                                        benutzer.TTL_username, 
                                        benutzer.TTL_password_md5)

        if TT_lock_tokens['success']:
            # Erfolgsfall: Verarbeiten Sie die zurückgegebenen Daten
            #benutzer.TTL_lock_id         = TT_lock_tokens['data']['lockId']
            benutzer.TTL_access_token    = TT_lock_tokens['data']['access_token']
            benutzer.TTL_refresh_token   = TT_lock_tokens['data']['refresh_token']

            TT_lock_list = get_lock_list(current_app.config['TTL_CLIENT_ID'], benutzer.TTL_access_token)
            # Durchsuchen der Liste und Auslesen der lockId, wenn der lockAlias gefunden wird
            lock_id = None
            for item in TT_lock_list['data']['list']:
                if item.get('lockAlias') == benutzer.TTL_lock_alias:
                    lock_id = item.get('lockId')
                    break

            # Überprüfen und Zuweisen der lockId
            if lock_id is not None:
                benutzer.TTL_lock_id = lock_id

            db.session.commit()
        else:
            pass
        
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

        lock_info = get_user_lockinfo(benutzer.CA_lock_id, session['access_token'])

        #print(lock_info)

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

                        lockupload = upload_lock_image(session['access_token'],filepath )
                        if lockupload['success']:  
                            combination_id = lockupload['data']['combinationId']
                            print(combination_id)
                            
                            udt = update_combination_relock(benutzer.CA_lock_id, session['access_token'], combination_id)
                            if udt['success']:
                                flash(f'Dein Chaster-Lock ist wieder verschlossen', 'success')


                        else:
                            print("Upload nicht ok!")



                        return redirect(url_for('home'))
                    else:
                        flash(f'Dein Chaster-Lock ist VERSCHLOSSEN', 'danger')
                        return redirect(url_for('home'))
            else:
                print("Keine Extension mit dem Slug 'temporary-opening' gefunden.")
        else:
            print("Die Antwort war nicht erfolgreich.")


@benutzer.route('/ttl_open/<uid>')
def ttl_open(uid):
    benutzer = Benutzer.query.filter_by(id=current_user.id).first()

    if benutzer.lock_uuid == uid:
        open_ttlock(current_app.config['TTL_CLIENT_ID'], benutzer.TTL_access_token,benutzer.TTL_lock_id)

        flash(f'Die UID {uid} ist korrekt und öffnet das TTLock!', 'success')
    else:
        flash(f'Die UID {uid} ist nicht korrekt das TTLock bleibt verschlossen!', 'danger')
    
    return redirect(url_for('home'))