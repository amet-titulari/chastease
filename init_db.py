from app import app
from database import db

# Erstellen eines Anwendungskontextes
with app.app_context():
    db.create_all()
