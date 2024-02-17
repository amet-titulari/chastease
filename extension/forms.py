#ca_extgension/forms.py
from flask_wtf import FlaskForm
from wtforms import StringField



class ExtensionConfigForm(FlaskForm):
  
    TTL_user = StringField('Username')
    TTL_pass = StringField('Password MD5')
    TTL_alias = StringField('Lock Alias')





