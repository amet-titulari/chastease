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

# FileHandler für die Log-Datei
file_handler = RotatingFileHandler('app.log', maxBytes=10000, backupCount=1)
file_handler.setLevel(numeric_level)
file_handler.setFormatter(logging.Formatter('%(asctime)s %(levelname)s: %(message)s'))

# StreamHandler für die Konsole
stream_handler = logging.StreamHandler()
stream_handler.setLevel(numeric_level)
stream_handler.setFormatter(logging.Formatter('%(asctime)s %(levelname)s: %(message)s'))

# Füge beide Handler zum Logger hinzu
logger.addHandler(file_handler)
logger.addHandler(stream_handler)
