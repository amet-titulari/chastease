import os

from app import app
from database import db

from flask_migrate import upgrade

# Pfad zur Datenbankdatei
database_path = './instance/database.sqlite'

# Erstellen eines Anwendungskontextes
with app.app_context():
    if not os.path.exists(database_path):
        # Datenbank erstellen...
        db.create_all()
       
    else:
        # Datenbank existiert bereits, führe Migrationen durch
        print("Führe Datenbank-Migrationen und Upgrades durch.")
        upgrade()
