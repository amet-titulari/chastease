#extgension/models.py

from database import db

class Session(db.Model):
        extension_id                  = db.Column(db.Integer, primary_key=True)


        benutzer_id = db.Column(db.Integer, db.ForeignKey('benutzer.id'), nullable=False)
        benutzer = db.relationship('Benutzer', backref=db.backref('benutzer', lazy=True))


