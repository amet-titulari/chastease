# benutzer/forms.py

from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField
from wtforms.validators import DataRequired

class BenutzerConfigForm(FlaskForm):
    CA_client_id = StringField('Client ID (CA)', validators=[DataRequired()])
    CA_client_secret = StringField('Client Secret (CA)', validators=[DataRequired()])
    CA_username = StringField('Username (CA)', validators=[DataRequired()])
    CA_user_id = StringField('User ID (CA)', validators=[DataRequired()])
    CA_lock_id = StringField('Lock ID (CA)', validators=[DataRequired()])

    TTL_client_id = StringField('Client ID (TTL)', validators=[DataRequired()])
    TTL_client_secret = StringField('Client Secret (TTL)', validators=[DataRequired()])
    TTL_username = StringField('Username (TTL)', validators=[DataRequired()])
    TTL_password_md5 = StringField('Password MD5 (TTL)', validators=[DataRequired()])
    TTL_lock_id = StringField('Lock ID (TTL)', validators=[DataRequired()])
    TTL_access_token = StringField('Access Token (TTL)')
    TTL_refresh_token = StringField('Refresh Token (TTL)')

    submit = SubmitField('Speichern')
