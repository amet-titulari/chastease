#ca_extgension/models.py

from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from . import db

class journal(db.Model):
    journal_id = db.Column(db.Integer, primary_key=True)
    boolesches_feld1 = db.Column(db.Boolean, default=False)
    boolesches_feld2 = db.Column(db.Boolean, default=False)
    boolesches_feld3 = db.Column(db.Boolean, default=False)
    boolesches_feld4 = db.Column(db.Boolean, default=False)
    freitextfeld = db.Column(db.String, nullable=True)

    # Hinzufügen des createdate-Feldes
    createdate = db.Column(db.DateTime, default=datetime.utcnow)

    # Fremdschlüsselbeziehung zur Benutzertabelle
    benutzer_id = db.Column(db.Integer, db.ForeignKey('benutzer.id'), nullable=False)
    benutzer = db.relationship('Benutzer', backref=db.backref('lock_history', lazy=True))

# Erstellen der Tabellen in der Datenbank
db.create_all()