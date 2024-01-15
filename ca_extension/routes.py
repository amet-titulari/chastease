from flask import Blueprint, Flask, request, jsonify


from flask import render_template

from . import ca_extension
from api.cahaster_extension import get_session_auth_info

@ca_extension.route('/')
def index():

    return render_template('ca_extension/index.html')


@ca_extension.route('/handle_token', methods=['POST'])
def handle_token():
    print(request.json)
    data = request.json
    main_token = data.get('mainToken')

    print(f'MainToken : {main_token}')

    sessioninfo = get_session_auth_info(main_token)
    #print(sessioninfo)

    if sessioninfo['success']:
        sessionId               = sessioninfo['data']['session']['sessionId']
        benutzername            = sessioninfo['data']['session']['lock']['user']['username']
        benutzerId              = sessioninfo['data']['session']['lock']['user']['_id']
        lock_status          = sessioninfo['data']['session']['lock']['status']

        print(f'SessionId: {sessionId} \nName: {benutzername} \nID {benutzerId} \nLock Status: {lock_status}')
        
    else:
        pass
    
    

    # Verarbeiten Sie hier den Token, z.B. speichern in der Datenbank, Authentifizierung, usw.
    # ...

    return jsonify({'status': 'Erfolg', 'message': 'Token empfangen'})


@ca_extension.route('/config', methods=['POST'])
def config():
    pass


@ca_extension.route('/hooks', methods=['POST'])
def hooks():
    pass