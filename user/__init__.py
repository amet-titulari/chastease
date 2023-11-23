from flask import Blueprint

# Erstellen eines Flask-Blueprints für das user-Modul
user_bp = Blueprint('user', __name__)

# Importieren der Routen, nachdem user_bp erstellt wurde, um zirkuläre Abhängigkeiten zu vermeiden
from . import routes
