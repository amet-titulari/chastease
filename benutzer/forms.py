# benutzer/forms.py

from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField
from wtforms.validators import DataRequired

class BenutzerConfigForm(FlaskForm):

    CA_username = StringField('Username')
    CA_keyholdername = StringField('Keyholder')
    CA_user_id = StringField('User ID', render_kw={'disabled': True})
    CA_lock_id = StringField('Lock ID', render_kw={'disabled': True})


    TTL_username = StringField('Username')
    TTL_password_md5 = StringField('Password MD5')
    TTL_lock_id = StringField('Lock ID', render_kw={'disabled': True})
    TTL_access_token = StringField('Access Token', render_kw={'disabled': True})
    TTL_refresh_token = StringField('Refresh Token', render_kw={'disabled': True})

    submit = SubmitField('Save')
