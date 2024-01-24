# benutzer/forms.py

from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField, BooleanField, IntegerField, DateTimeField, HiddenField
from wtforms.validators import DataRequired

class BenutzerConfigForm(FlaskForm):

    CA_username = StringField('Username', render_kw={'disabled': True})
    CA_keyholdername = StringField('Keyholder' , render_kw={'disabled': True})
    CA_keyholder_id = StringField('Keyholder ID' ,render_kw={'disabled': True})
    CA_user_id = StringField('User ID', render_kw={'disabled': True})
    CA_lock_id = StringField('Lock ID', render_kw={'disabled': True})


    TTL_username = StringField('Username')
    TTL_password_md5 = StringField('Password MD5')
    TTL_lock_alias = StringField('Lock Alias')

    submit = SubmitField('Submit')


class JournalAddForm(FlaskForm):
    hygiene = BooleanField('Hygiene')
    shave = BooleanField('Shave')
    edge = BooleanField('Edge')
    ruined = BooleanField('Ruined')
    orgasm = BooleanField('Orgasm')
    horny = IntegerField('Horny', validators=[DataRequired()])
    note = StringField('Note')
    submit = SubmitField('Submit')


class JournalEditForm(FlaskForm):
    journal_id = HiddenField()
    hygiene = BooleanField('Hygiene')
    shave = BooleanField('Shave')
    edge = BooleanField('Edge')
    ruined = BooleanField('Ruined')
    orgasm = BooleanField('Orgasm')
    horny = IntegerField('Horny', )
    note = StringField('Note')
    created_at = DateTimeField('created_at',validators=[DataRequired()])
    submit = SubmitField('Submit')
