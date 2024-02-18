#extgension/models.py
from database import db

class ChasterSession(db.Model):
    id                  = db.Column(db.String(64), primary_key=True)
    user_id             = db.Column(db.Integer, db.ForeignKey('benutzer.id'), nullable=False)
    username            = db.Column(db.String(100), unique=True)
    keyholder_id        = db.Column(db.Integer, db.ForeignKey('benutzer.id'), nullable=True)
    lock_uuid           = db.Column(db.String(128))

    # Konfigurationsfelder für Chaster.app
    lock_id             = db.Column(db.String(128))
    lock_status         = db.Column(db.String(16))
    combination_id      = db.Column(db.String(128)) 

    # Konfiguration für TTLock
    TTL_username        = db.Column(db.String(128))
    TTL_password_md5    = db.Column(db.String(128))
    TTL_lock_alias      = db.Column(db.String(128))
    TTL_lock_id         = db.Column(db.String(128))
