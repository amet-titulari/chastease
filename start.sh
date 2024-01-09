#!/bin/bash

# Beendet das Skript bei Fehlern
set -e

# Überprüfen, ob database.sqlite im Verzeichnis ./instance existiert
if [ ! -f ./instance/database.sqlite ]; then
    echo "database.sqlite existiert nicht, führe Initialisierungen aus..."
    python init_db.py
    #flask db init
    #flask db migrate
    flask db upgrade
else
    echo "database.sqlite existiert bereits, führe nur Upgrade aus..."
    flask db upgrade
fi

# Starten der Flask-Anwendung
#flask run --host=0.0.0.0
gunicorn -w 4 -b 0.0.0.0:5000 app:app
