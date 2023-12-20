# benutzer/forms.py

from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField
from wtforms.validators import DataRequired

class BenutzerConfigForm(FlaskForm):
    CA_client_id = StringField('Client ID (CA)')
    CA_client_secret = StringField('Client Secret (CA)')
    CA_username = StringField('Username (CA)')
    CA_user_id = StringField('User ID (CA)')
    CA_lock_id = StringField('Lock ID (CA)')

    TTL_client_id = StringField('Client ID (TTL)')
    TTL_client_secret = StringField('Client Secret (TTL)')
    TTL_username = StringField('Username (TTL)')
    TTL_password_md5 = StringField('Password MD5 (TTL)')
    TTL_lock_id = StringField('Lock ID (TTL)')
    TTL_access_token = StringField('Access Token (TTL)')
    TTL_refresh_token = StringField('Refresh Token (TTL)')

    submit = SubmitField('Speichern')
