from database import db

from datetime import datetime
import pytz
from sqlalchemy.sql import func

from flask_login import UserMixin

class Benutzer(UserMixin, db.Model):
    id                  = db.Column(db.Integer, primary_key=True)
    username            = db.Column(db.String(100), unique=True)
    role                = db.Column(db.String(100), unique=False)
    avatarUrl           = db.Column(db.String(100), unique=False)
    lock_uuid           = db.Column(db.String(128))

    # Konfigurationsfelder für Chaster.app
    CA_username         = db.Column(db.String(128))
    CA_keyholdername    = db.Column(db.String(128))
    CA_keyholder_id     = db.Column(db.String(128))
    CA_user_id          = db.Column(db.String(128))
    CA_lock_id          = db.Column(db.String(128))
    CA_lock_status      = db.Column(db.String(16))
    CA_combination_id   = db.Column(db.String(128)) 

    # Konfiguration für TTLock
    TTL_username        = db.Column(db.String(128))
    TTL_password_md5    = db.Column(db.String(128))
    TTL_lock_alias      = db.Column(db.String(128))
    TTL_lock_id         = db.Column(db.String(128))

class LockHistory(db.Model):
    hist_id              = db.Column(db.String(128), primary_key=True)
    benutzer_id          = db.Column(db.Integer, db.ForeignKey('benutzer.id'), nullable=False)

    lock_id              = db.Column(db.String(128))
    type                 = db.Column(db.String(128))
    created_at           = db.Column(db.String(128))
    extension            = db.Column(db.String(128))
    title                = db.Column(db.String(128))
    description          = db.Column(db.String(128))
    icon                 = db.Column(db.String(128))
    
    # Weitere Felder für Ihre Historie...
    benutzer = db.relationship('Benutzer', backref=db.backref('lock_history', lazy=True))


class Journal(db.Model):
    journal_id          = db.Column(db.Integer, primary_key=True)
    benutzer_id         = db.Column(db.Integer, db.ForeignKey('benutzer.id'), nullable=False)
    
    shave               = db.Column(db.Boolean, default=False)
    edge                = db.Column(db.Boolean, default=False)
    ruined              = db.Column(db.Boolean, default=False)
    orgasm              = db.Column(db.Boolean, default=False)
    horny               = db.Column(db.Integer, default=6)
    note                = db.Column(db.String, nullable=True)
    created_at          = db.Column(db.DateTime(timezone=True), server_default=func.now())
    
    # Weitere Felder für Ihre Historie...
    benutzer = db.relationship('Benutzer', backref=db.backref('journal', lazy=True))


