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


# StreamHandler für die Konsole
stream_handler = logging.StreamHandler()
stream_handler.setLevel(numeric_level)
stream_handler.setFormatter(logging.Formatter('%(asctime)s %(levelname)s: %(message)s'))

# Füge beide Handler zum Logger hinzu
logger.addHandler(stream_handler)

# Beispiel für Logging
#logger.debug("Debug-Nachricht")
#logger.info("Info-Nachricht")
#logger.warning("Warn-Nachricht")
#logger.error("Fehler-Nachricht")
#logger.critical("Kritische-Nachricht")
