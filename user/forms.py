from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField, ValidationError
from wtforms.validators import DataRequired, Email, EqualTo, Length

class LoginForm(FlaskForm):
    username = StringField('Benutzername', validators=[DataRequired(message="Benutzername ist erforderlich.")])
    password = PasswordField('Passwort', validators=[DataRequired(message="Passwort ist erforderlich.")])
    submit = SubmitField('Anmelden')

class RegistrationForm(FlaskForm):
    email = StringField('Email', validators=[
        DataRequired(message="Email ist erforderlich."),
        Email(message="Bitte geben Sie eine gültige Email-Adresse ein.")
    ])
    username = StringField('Benutzername', validators=[
        DataRequired(message="Benutzername ist erforderlich."),
        Length(min=4, max=25, message="Benutzername muss zwischen 4 und 25 Zeichen lang sein.")
    ])
    password = PasswordField('Passwort', validators=[
        DataRequired(message="Passwort ist erforderlich."),
        Length(min=6, message="Passwort muss mindestens 6 Zeichen lang sein.")
    ])
    confirm_password = PasswordField('Passwort bestätigen', validators=[
        DataRequired(message="Passwortbestätigung ist erforderlich."),
        EqualTo('password', message="Passwörter müssen übereinstimmen.")
    ])
    submit = SubmitField('Registrieren')

    # Optional: Benutzerdefinierte Validierungsfunktionen
    def validate_username(self, username):
        # Logik zur Überprüfung, ob der Benutzername bereits existiert
        pass

    def validate_email(self, email):
        # Logik zur Überprüfung, ob die Email bereits existiert
        pass
