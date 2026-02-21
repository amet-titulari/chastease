# chastease

Modernes KI-gestuetztes Rollenspiel mit Flask-API als Backend.
Dieses Repository ist die gemeinsame Basis fuer Implementierung, Planung und Dokumentation.

## Projektziele

- Flask-basierte API fuer ein modulares RPG
- KI-gestuetzter Story/Game-Master-Loop
- Persistente Spielstaende und Weltzustaende
- Saubere Architektur mit klaren Domänenmodulen

## Tech-Stack (Start)

- Python 3.12+
- Flask
- Pytest

Erweiterungen fuer die naechsten Schritte:
- SQLAlchemy + Alembic
- PostgreSQL
- Redis Queue (Background Jobs)
- OpenAI API Integration

## Schnellstart

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python run.py
```

API laeuft dann auf `http://127.0.0.1:5000`.

Healthcheck:

```bash
curl http://127.0.0.1:5000/api/v1/health
```

## Tests

```bash
pytest
```

## Struktur

```text
src/chastease/
  api/                 # REST-Endpunkte
  config.py            # Konfiguration
  __init__.py          # App-Factory
tests/                 # API- und Service-Tests
docs/
  PRODUCT_VISION.md
  ARCHITECTURE.md
  PROJECT_PLAN.md
  BACKLOG.md
```

## Dokumentation

- Produktvision: `docs/PRODUCT_VISION.md`
- Architektur: `docs/ARCHITECTURE.md`
- Umsetzungsplan (MVP): `docs/PROJECT_PLAN.md`
- Backlog: `docs/BACKLOG.md`
