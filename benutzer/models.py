# benutzer/models.py
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin

db = SQLAlchemy()
class Benutzer(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True)
    password = db.Column(db.String(100))
class BenutzerConfig(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    benutzer_id = db.Column(db.Integer, db.ForeignKey('benutzer.id'))  # Verknüpfung mit der Benutzer-Tabelle
    benutzer = db.relationship('Benutzer', backref=db.backref('config', lazy=True))

    # Konfigurationsfelder
    CA_client_id = db.Column(db.String(128))
    CA_client_secret = db.Column(db.String(128))
    CA_username = db.Column(db.String(128))
    CA_user_id = db.Column(db.String(128))
    CA_lock_id = db.Column(db.String(128))

    TTL_client_id = db.Column(db.String(128))
    TTL_client_secret = db.Column(db.String(128))
    TTL_username = db.Column(db.String(128))
    TTL_password_md5 = db.Column(db.String(128))
    TTL_lock_id = db.Column(db.String(128))
    TTL_access_token = db.Column(db.String(256))
    TTL_refresh_token = db.Column(db.String(256))