#ca_extgension/forms.py
from flask_wtf import FlaskForm
from wtforms import StringField



class ExtensionConfigForm(FlaskForm):
  
    TTL_username = StringField('Username')
    TTL_password_md5 = StringField('Password MD5')
    TTL_lock_alias = StringField('Lock Alias')





