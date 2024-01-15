import logging
from logging.handlers import RotatingFileHandler
import os
from dotenv import load_dotenv

# Laden der Umgebungsvariablen
load_dotenv()

# Logger-Konfiguration
logger = logging.getLogger('app')
log_level = os.getenv('LOG_LEVEL', 'DEBUG').upper()
numeric_level = getattr(logging, log_level, None)

if not isinstance(numeric_level, int):
    raise ValueError(f'Invalid log level: {log_level}')

logger.setLevel(numeric_level)

# Pfad zum Log-Verzeichnis festlegen
log_directory = '/log'  # Ersetzen Sie dies mit Ihrem gewünschten Verzeichnis

# Überprüfen, ob das Verzeichnis existiert, und falls nicht, erstellen
#if not os.path.exists(log_directory):
#    os.makedirs(log_directory)

# Vollständigen Pfad zur Log-Datei definieren
#log_file_path = os.path.join(log_directory, 'app.log')

# FileHandler für die Log-Datei
#file_handler = RotatingFileHandler(log_file_path, maxBytes=10000, backupCount=1)
#file_handler.setLevel(numeric_level)
#file_handler.setFormatter(logging.Formatter('%(asctime)s %(levelname)s: %(message)s'))

# StreamHandler für die Konsole
stream_handler = logging.StreamHandler()
stream_handler.setLevel(numeric_level)
stream_handler.setFormatter(logging.Formatter('%(asctime)s %(levelname)s: %(message)s'))

# Füge beide Handler zum Logger hinzu
logger.addHandler(file_handler)   # Schreiben in Filesystem noch nicht erwünscht
logger.addHandler(stream_handler)

# Beispiel für Logging
#logger.debug("Debug-Nachricht")
#logger.info("Info-Nachricht")
#logger.warning("Warn-Nachricht")
#logger.error("Fehler-Nachricht")
#logger.critical("Kritische-Nachricht")
