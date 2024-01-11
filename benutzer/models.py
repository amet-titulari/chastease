from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin

db = SQLAlchemy()

class Benutzer(UserMixin, db.Model):
    id                  = db.Column(db.Integer, primary_key=True)
    username            = db.Column(db.String(100), unique=True)
    role                = db.Column(db.String(100), unique=False)
    lock_uuid           = db.Column(db.String(128))

    # Konfigurationsfelder für Chaster.app
    CA_username         = db.Column(db.String(128))
    CA_keyholdername    = db.Column(db.String(128))
    CA_keyholder_id     = db.Column(db.String(128))
    CA_user_id          = db.Column(db.String(128))
    CA_lock_id          = db.Column(db.String(128))
    CA_lock_status      = db.Column(db.String(16))
    CA_combination_id   = db.Column(db.String(128)) 
    CA_lasthist_id      = db.Column(db.String(128))

    # Konfiguration für TTLock
    TTL_username        = db.Column(db.String(128))
    TTL_password_md5    = db.Column(db.String(128))
    TTL_lock_alias      = db.Column(db.String(128))
    TTL_lock_id         = db.Column(db.String(128))

class CA_Lock_History(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    benutzer_id = db.Column(db.Integer, db.ForeignKey('benutzer.id'), nullable=False)
    # Weitere Felder für Ihre Historie...
    benutzer = db.relationship('Benutzer', backref=db.backref('lock_history', lazy=True))

    hist_id              = db.Column(db.String(128))
    lock_id              = db.Column(db.String(128))
    type                 = db.Column(db.String(128))
    created_at           = db.Column(db.String(128))
    extension            = db.Column(db.String(128))
    title                = db.Column(db.String(128))
    description          = db.Column(db.String(128))
    icon                 = db.Column(db.String(128))
    



