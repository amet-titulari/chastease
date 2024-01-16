from flask import  request, jsonify, current_app, session


from flask import render_template

from . import extension
from api.cahaster_extension import get_session_auth_info, get_session_info

@extension.route('/')
def index():

    content = f'    <div class="container">\
                        <h1>Das ist die Erweiterung!!</h1>\
                        <h3></h3>\
                        <p></p>\
                    </div>'

    return render_template('index.html', content=content) 




@extension.route('/handle_token', methods=['POST'])
def handle_token():

    data = request.json
    main_token = data.get('mainToken')

    print(f'MainToken : {main_token}')

    sessionauth = get_session_auth_info(main_token)

    #print(sessionauth)

    if sessionauth['success']:
        sessionId               = sessionauth['data']['session']['sessionId']
        benutzername            = sessionauth['data']['session']['lock']['user']['username']
        benutzerId              = sessionauth['data']['session']['lock']['user']['_id']
        lock_status             = sessionauth['data']['session']['lock']['status']

        print(f'SessionId: {sessionId} \nName: {benutzername} \nID {benutzerId} \nLock Status: {lock_status}')

        sessioninfo = get_session_info(sessionId)
        #sprint(sessioninfo)

        reasonsPreventingUnlocking = sessioninfo['data']['session']['lock']['reasonsPreventingUnlocking'] 

        for reasonNoUnlock in reasonsPreventingUnlocking:
            print(reasonNoUnlock)
            if reasonNoUnlock['reason'] == 'temporary_opening':
                print(f'Das Schloss der {sessionId} ist Temporär geöffnet!')
            else:
                print(f'Das Schloss der {sessionId} ist VERSCHLOSSEN!')



    else:
        pass
    
    

    # Verarbeiten Sie hier den Token, z.B. speichern in der Datenbank, Authentifizierung, usw.
    # ...

    return jsonify({'status': 'Erfolg', 'message': 'Token empfangen'})


@extension.route('/config', methods=['POST'])
def config():
    pass


@extension.route('/hooks', methods=['POST'])
def hooks():
    pass