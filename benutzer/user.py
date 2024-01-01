# benutzer/user.py
import json
import re
import hashlib
from flask import Blueprint, current_app, render_template, redirect, request, flash, url_for
from flask_login import login_required, current_user
from .models import db, Benutzer, BenutzerConfig
from .forms import BenutzerConfigForm
from api.chaster import get_user_profile, get_user_lockid, get_user_lockinfo
from api.ttlock import get_ttlock_tokens

import os


benutzer = Blueprint('benutzer', __name__)

def is_md5(s):
    return bool(re.match(r'^[a-fA-F0-9]{32}$', s))


@benutzer.route('/config', methods=['GET', 'POST'])
@login_required
def config():
    benutzer_config = BenutzerConfig.query.filter_by(benutzer_id=current_user.id).first()
    form = BenutzerConfigForm(obj=benutzer_config)

    if request.method == 'POST' and form.validate_on_submit():
        # Hier fügen Sie den Code ein, der ausgeführt wird, wenn das Formular gesendet wird.
        # Dies beinhaltet die Aktualisierung der Benutzerkonfigurationen und das Speichern in der Datenbank.
        # ...

        # Nach dem Speichern der Daten könnten Sie eine Bestätigungsnachricht anzeigen oder zu einer anderen Seite umleiten.

        if form.validate_on_submit():
            if form.TTL_username.data:
                benutzer_config.TTL_username = form.TTL_username.data

            if form.TTL_password_md5.data:
                if not is_md5(form.TTL_password_md5.data):
                    # MD5-Hash des Passworts erzeugen, wenn es kein MD5-Hash ist
                    hashed_password = hashlib.md5(form.TTL_password_md5.data.encode()).hexdigest()
                    benutzer_config.TTL_password_md5 = hashed_password
                else:
                    # Direkt zuweisen, wenn es bereits ein MD5-Hash ist
                    benutzer_config.TTL_password_md5 = form.TTL_password_md5.data

        db.session.commit()
        flash('Konfiguration aktualisiert!', 'success')
        return redirect(url_for('benutzer.config'))


    # Wenn die Methode GET ist oder das Formular nicht validiert, wird die Seite normal angezeigt.
    # Dieser Teil des Codes lädt die aktuellen Benutzerdaten und zeigt das Formular an.
    # ...

    if not benutzer_config:
        benutzer_config = BenutzerConfig(benutzer_id=current_user.id)
        db.session.add(benutzer_config)
        #flash('Benutzer angelegt!', 'success')
    else:
        #flash('Benutzer besteht!', 'info')
        pass


    profile_data = get_user_profile(current_user.username, current_app.config['CA_CLIENT_ID'], current_app.config['CA_CLIENT_SECRET'])

    if profile_data['success']:
        # Erfolgsfall: Verarbeiten Sie die zurückgegebenen Daten
        benutzer_config.CA_user_id = profile_data['data'].get('_id')
        benutzer_config.CA_username = profile_data['data'].get('username')
        db.session.commit()
        flash('Benutzerprofil erfolgreich aktualisiert.', 'success')
    else:
        # Fehlerfall: Zeigen Sie eine Fehlermeldung an
        flash(f'Fehler beim Abrufen des Benutzerprofils: {profile_data["error"]}', 'danger')


    # Zweiter API-Aufruf für Lock-Daten 
    lock_data = get_user_lockid(benutzer_config.CA_user_id, current_app.config['CA_CLIENT_ID'], current_app.config['CA_CLIENT_SECRET'])

    if lock_data['success']:
        # Erfolgsfall: Verarbeiten Sie die zurückgegebenen Daten
        # Stellen Sie sicher, dass die Antwort die erwarteten Daten enthält
        if lock_data['data']:
            benutzer_config.CA_lock_id = lock_data['data'][0].get('_id')
            benutzer_config.CA_lock_status = lock_data['data'][0].get('status')
            benutzer_config.CA_lock_combination = lock_data['data'][0].get('combination')

            db.session.commit()
            flash('Konfiguration der Profildaten erstellt!', 'success')
        else:
            # Falls die Antwort leer ist oder die erwarteten Daten nicht enthält
            flash('Die Antwort enthält keine Lock-Daten.', 'warning')
    else:
        # Fehlerfall: Zeigen Sie eine Fehlermeldung an
        flash(f'Fehler beim Abrufen der Lock-Daten: {lock_data["error"]}', 'danger')

    lock_info = get_user_lockinfo(benutzer_config.CA_lock_id, current_user.CA_access_token)

    if lock_info['success']:
        # Überprüfen, ob die Antwort die notwendigen 'keyholder' Informationen enthält
        if 'keyholder' in lock_info['data']:
            benutzer_config.CA_keyholder_id = lock_info['data']['keyholder']['_id']
            benutzer_config.CA_keyholdername = lock_info['data']['keyholder']['username']

            db.session.commit()
            flash('Keyholder Profil ermittelt!', 'success')
        else:
            # Falls die 'keyholder' Informationen nicht in der Antwort vorhanden sind
            flash('Keine Keyholderinformationen vorhanden.', 'info')
    else:
        # Fehlerfall: Zeigen Sie eine Fehlermeldung an
        flash(f'Fehler beim Abrufen der Lock-Informationen: {lock_info["error"]}', 'danger')


    # TT Lockinfo
    if benutzer_config.TTL_username and benutzer_config.TTL_password_md5:
        TT_lock_info = get_ttlock_tokens(current_app.config['TTL_CLIENT_ID'], 
                                        current_app.config['TTL_CLIENT_SECRET'], 
                                        benutzer_config.TTL_username, 
                                        benutzer_config.TTL_password_md5)

        if TT_lock_info['success']:
            # Erfolgsfall: Verarbeiten Sie die zurückgegebenen Daten
            benutzer_config.TTL_access_token = TT_lock_info['data']['access_token']
            benutzer_config.TTL_refresh_token = TT_lock_info['data']['refresh_token']

            db.session.commit()
            #flash('TTLOCK Konfiguration erfolgreich aufgerufen', 'success')
        else:
            # Fehlerfall: Zeigen Sie eine Fehlermeldung an
            flash(f'TTLOCK Konfigurationsfehler: {TT_lock_info["error"]}', 'danger')
    
    # Formulardaten aktualisieren
    form = BenutzerConfigForm(obj=benutzer_config)
    return render_template('benutzerconfig.html', form=form)


