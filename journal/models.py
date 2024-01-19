#ca_extgension/models.py

from datetime import datetime
from database import db

class Journal(db.Model):
    journal_id = db.Column(db.Integer, primary_key=True)
    shave            = db.Column(db.Boolean, default=False)
    edge             = db.Column(db.Boolean, default=False)
    ruined           = db.Column(db.Boolean, default=False)
    orgasm           = db.Column(db.Boolean, default=False)
    journal          = db.Column(db.String, nullable=True)

    # Hinzufügen des createdate-Feldes
    createdate = db.Column(db.DateTime, default=datetime.utcnow)

    # Fremdschlüsselbeziehung zur Benutzertabelle
    benutzer_id = db.Column(db.Integer, db.ForeignKey('benutzer.id'), nullable=False)
    benutzer = db.relationship('Benutzer', backref=db.backref('journal_id', lazy=True))
