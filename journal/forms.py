from flask_wtf import FlaskForm
from wtforms import BooleanField, StringField, SubmitField, TextAreaField, HiddenField
from wtforms.validators import DataRequired

class JournalForm(FlaskForm):
    shave = BooleanField('Shave')
    edge = BooleanField('Edge')
    ruined = BooleanField('Ruined')
    orgasm = BooleanField('Orgasm')
    journal = TextAreaField('Journal')
    benutzer_id = HiddenField('Benutzer ID', validators=[DataRequired()])  
    submit = SubmitField('Speichern')
