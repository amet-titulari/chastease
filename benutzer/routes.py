# benutzer/routes.py

import re
import hashlib
from pytz import timezone
from sqlalchemy import desc

from database import db

from flask import  current_app, session, redirect, request, flash, url_for,render_template, jsonify
from flask_login import login_required, login_user, current_user


from helper.log_config import logger

from . import benutzer
from .token_handling import refresh_ca_token, refresh_ttl_token

from .models import Benutzer,  Journal, History_Chaster, History_TTLock
from .forms import BenutzerConfigForm, BenutzerConfigFormTTL ,JournalAddForm, JournalEditForm
from .qrcode import generate_qr

from api.ttlock import get_lock_list, get_gateway_list, open_ttlock

from benutzer.token_handling import get_ttlock_tokens


def is_md5(s):
    return bool(re.match(r'^[a-fA-F0-9]{32}$', s))

@benutzer.route('/config', methods=['GET', 'POST'])
@login_required
def config():
    
    from api.chaster import get_user_profile, get_user_lockid, get_user_lockinfo

    benutzer = Benutzer.query.filter_by(id=current_user.id).first()
    form = BenutzerConfigForm(obj=benutzer)

    if request.method == 'POST' and form.validate_on_submit():
        # Formularverarbeitung für POST-Anfrage
        benutzer.TTL_username = form.TTL_username.data or benutzer.TTL_username

        if form.TTL_password_md5.data:
            benutzer.TTL_password_md5 = (hashlib.md5(form.TTL_password_md5.data.encode()).hexdigest() 
                                         if not is_md5(form.TTL_password_md5.data) 
                                         else form.TTL_password_md5.data)
            
        db.session.commit()

        if not benutzer.TTL_lock_id:
           return redirect(url_for('benutzer.config_ttl')) 


        form = BenutzerConfigForm(obj=benutzer)

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
    #print(lock_info)

    if lock_info['success']:
        
        if lock_info['data']['keyholder'] is not None:

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
   
    form = BenutzerConfigForm(obj=benutzer)
    return render_template('benutzerconfig.html', form=form)

@benutzer.route('/config_ttl', methods=['GET', 'POST'])
@login_required
def config_ttl():

    try:
        gettoken = get_ttlock_tokens()

        if not gettoken:
            flash('Konfiguration aktualisiert!', 'success')
        
        else:

            TTL_lock_list = get_lock_list(current_app.config['TTL_CLIENT_ID'], session['ttl_access_token'])
            TTL_gateway_list = get_gateway_list(current_app.config['TTL_CLIENT_ID'], session['ttl_access_token'])

            # Alle Schlösser auslesen
            locks = [
                ( lock['lockId'], lock['lockAlias'])
                for lock in TTL_lock_list['data']['list']
            ]

            # Alle Gateway's auslesen
            gateways = [
                (gateway['gatewayId'], gateway['gatewayName'])
                for gateway in TTL_gateway_list['data']['list']
            ]

            #print(f'Schlösser: {locks}\n')
            #print(f'Gateways: {gateways}\n')

            form = BenutzerConfigFormTTL()

            form.TTL_lock.choices = locks
            form.TTL_gateway.choices = gateways

            benutzer = Benutzer.query.filter_by(id=current_user.id).first()
    

        if form.validate_on_submit():
            # Formularverarbeitung für POST-Anfrage
            benutzer.TTL_username = benutzer.TTL_username

            benutzer.TTL_lock_id = form.TTL_lock.data
            benutzer.TTL_gateway_id = form.TTL_gateway.data
            db.session.commit()
            flash('Konfiguration aktualisiert!', 'success')

        return render_template('benutzerconfig_ttl.html', form=form )
    
    except:
        e= "Es ist ein Fehler aufetreten!"
        return {'success': False, 'error': f' {str(e)}'}
   
@benutzer.route('/relock')
@login_required
def relock():

    
    from api.chaster import get_user_lockinfo, update_combination_relock, upload_lock_image

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
#@login_required
def ttl_open(uid):

    benutzer = Benutzer.query.filter_by(lock_uuid=uid).first()

    
    if benutzer and benutzer.lock_uuid == uid:
        login_user(benutzer)  # Meldet den Benutzer an
    
        session['ca_refresh_token'] = benutzer.CA_refresh_token
        session['ttl_refresh_token'] = benutzer.TTL_refresh_token
    
        refresh_ca_token()
        refresh_ttl_token()

        open_ttlock()

        flash(f'Die UID {uid} ist korrekt und öffnet das TTLock!', 'success')
        content = f'<div class="container text-start">\
                <h1>Hallo {current_user.username}</h1>\
                <h3>Du kannst deine Hygeneöffnung jetzt durchführen</h3>\
                <p>Viel Glück</p>\
                </p>\
                <a href="/user/relock" class="btn btn-info" role="button">Relock Session</a>\
            </div>'
    else:
        flash(f'Die UID {uid} ist nicht korrekt das TTLock bleibt verschlossen!', 'danger')
        content = f'<div class="container text-start">\
                <h1>Hallo {current_user.username}</h1>\
                <h3>Du hast einen falschen QR Code verwendet!</h3>\
                <p>Viel Glück beim nächsten mal!</p>\
                </p>\
            </div>'
      
    return render_template('index.html', content=content) 

@benutzer.route('/history')
@login_required
def get_lockhistory():
        
        chaster = History_Chaster.query.filter_by(benutzer_id=current_user.id).order_by(desc(History_Chaster.created_at)).all()
        ttlock = History_TTLock.query.filter_by(benutzer_id=current_user.id).order_by(desc(History_TTLock.created_at)).all()

        return render_template('history_view.html', chaster=chaster, ttlock=ttlock)

@benutzer.route('/update_history')
@login_required
def update_lockhistory():
    print("Update gestartet!")
    from api.chaster import get_chaster_history
    from api.ttlock import get_ttlock_history

    chaster_history = get_chaster_history()
    if chaster_history['success']:
        pass
    else:
        flash('Fehler beim Aktualisieren der CHASTER Lock-Historie', 'danger')

    ttlock_history = get_ttlock_history()
    if ttlock_history['success']:
        pass
    else:
        flash('Fehler beim Aktualisieren der TTLock-Historie', 'danger')

    return jsonify({'success': True})


@benutzer.route('/journal_add', methods=['GET', 'POST'])
@login_required
def journal_add():
    
    form = JournalAddForm()
    if form.validate_on_submit():
        # Erstellen eines neuen Journal-Objekts mit den Daten aus dem Formular
        new_journal = Journal(
            benutzer_id=current_user.id,
            shave=form.shave.data,
            edge=form.edge.data,
            ruined=form.ruined.data,
            orgasm=form.orgasm.data,
            horny=form.horny.data,
            note=form.note.data
        )

        # Hinzufügen des neuen Objekts zur Datenbanksitzung und Speichern in der Datenbank
        db.session.add(new_journal)
        db.session.commit()

        flash('Journal-Eintrag erfolgreich hinzugefügt!', 'success')
        return redirect(url_for('benutzer.journal_view'))

    return render_template('journal_add.html', form=form)

@benutzer.route('/journal_view')
@login_required
def journal_view():
    journals = Journal.query.order_by(desc(Journal.created_at)).all()
    for journal in journals:
        if journal.created_at:
            journal.created_at = journal.created_at.astimezone(timezone('Europe/Zurich'))
    return render_template('journal_view.html', journals=journals)

@benutzer.route('/journal_edit/<int:journal_id>', methods=['GET', 'POST'])
@login_required
def journal_edit(journal_id):
    journal = Journal.query.get_or_404(journal_id) 
    form = JournalEditForm(obj=journal)
    form.journal_id.data = journal_id
    if form.validate_on_submit():
        # Formulardaten in das Journal-Objekt übertragen
        form.populate_obj(journal)

        if form.created_at.data:
            journal.created_at = form.created_at.data

        db.session.commit()  # Aktualisieren Sie den Eintrag in der Datenbank
        flash('Journal-Eintrag aktualisiert.', 'success')  # Optional: Erfolgsmeldung anzeigen
        return redirect(url_for('benutzer.journal_view'))  # Umleitung zur Journal-Übersicht

    # Wenn die Anfrage eine GET-Anfrage ist, rendern Sie das Formular mit den Daten des Journals
    return render_template('journal_edit.html', form=form)

@benutzer.route('/journal_delete/<int:journal_id>', methods=['GET', 'POST'])
def delete_journal(journal_id):

    journal = Journal.query.get(journal_id)
    if journal:
        db.session.delete(journal)
        db.session.commit()
        flash("Eintrag gelöscht",'success')
    else:
        flash("Eintrag konnte nicht gelöscht werden!",'danger')

    # Weiterleitung zurück zur Hauptseite oder zu einer anderen relevanten Seite
    return redirect(url_for('benutzer.journal_view'))
