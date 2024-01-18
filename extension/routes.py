from flask import  request, jsonify, current_app, session, render_template, redirect, url_for, flash
from flask_login import login_user, current_user

from . import extension
from .models import db


from benutzer.models import Benutzer

from api.cahaster_extension import get_session_auth_info, get_session_info

@extension.route('/')
def index():

    print(current_user.is_authenticated)

    content = f'    <div class="container">\
                        <h1>Infos zur Erweiterungssession!</h1>\
                        <h3></h3>\
                        <p></p>\
                    </div>'

    return redirect(url_for('extension.handle_token'))
 




@extension.route('/handle_token', methods=['GET','POST'])
def handle_token():


    if request.method == 'POST':
        data = request.json
        main_token = data.get('mainToken')

        session['main_token'] = main_token
        sessionauth = get_session_auth_info(main_token)

        # Extrahieren des 'data'-Teils
        if sessionauth['success']:
            data = sessionauth['data']

            sessionId  = sessionauth['data']['session']['sessionId']
            username    = sessionauth['data']['session']['lock']['user']['username']
            role        = sessionauth['data']['session']['lock']['user']['role']
            avatarUrl  = sessionauth['data']['session']['lock']['user']['avatarUrl']


        else:
            print("Fehler: Die Antwort war nicht erfolgreich.")


        benutzer = Benutzer.query.filter_by(username=username).first()
        
        if not benutzer:
            benutzer = Benutzer(username=username, role=role, avatarUrl=avatarUrl)
            db.session.add(benutzer)
            db.session.commit()
            login_user(benutzer)    

        else: 
            benutzer.username = username
            benutzer.role = role
            benutzer.avatarUrl = avatarUrl    
            db.session.commit()
            login_user(benutzer)  


        if current_user.is_authenticated:
            print("Anmeldung ok")
        else:
            print("Anmeldung nicht erfolgt")


        sessioninfo = get_session_info(sessionId)

        print(f'Current Username : {current_user.username} \nAvatar Url: {current_user.avatarUrl} \nRolle: {current_user.role}  ')

        reasonsPreventingUnlocking = sessioninfo['data']['session']['lock']['reasonsPreventingUnlocking'] 

        for reasonNoUnlock in reasonsPreventingUnlocking:
            print(reasonNoUnlock)
            if reasonNoUnlock['reason'] == 'temporary_opening':
                flash(f'Das Schloss der {sessionId} ist Temporär geöffnet!')
            else:
                flash(f'Das Schloss der {sessionId} ist VERSCHLOSSEN!')

      
        print(current_user.__dict__)


        print(f'Weiterleitung\n\n')      
        return render_template('extension/session.html', content=current_user.__dict__)
    
    if request.method == 'GET':

        content = {"Wert1":"Inhalt von Wert1"}

        flash("Willkommen")



        return render_template('extension/session.html', content=content)

    
  

@extension.route('/config', methods=['POST'])
def config():
    pass


@extension.route('/hooks', methods=['POST'])
def hooks():
    pass