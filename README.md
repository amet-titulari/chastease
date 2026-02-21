# chastease

Modernes KI-gestuetztes Rollenspiel mit Python-API als Backend (FastAPI Zielarchitektur).
Dieses Repository ist die gemeinsame Basis fuer Implementierung, Planung und Dokumentation.

## Projektziele

- Python-basierte API fuer ein modulares RPG
- KI-gestuetzter Story/Game-Master-Loop
- Persistente Spielstaende und Sitzungszustaende
- Saubere Architektur mit klaren Domänenmodulen

## Tech-Stack (Start)

- Python 3.12+
- FastAPI
- Uvicorn
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

Setup-Prototyp:

```bash
# 1) Setup starten
curl -X POST http://127.0.0.1:5000/api/v1/setup/sessions \
  -H "Content-Type: application/json" \
  -d '{"wearer_id":"wearer-1","hard_stop_enabled":true,"autonomy_mode":"execute","language":"de","integrations":["ttlock"],"blocked_trigger_words":["public"],"forbidden_topics":["workplace"]}'

# 2) Antworten senden
curl -X POST http://127.0.0.1:5000/api/v1/setup/sessions/<setup_session_id>/answers \
  -H "Content-Type: application/json" \
  -d '{"answers":[{"question_id":"q1_rule_structure","value":8},{"question_id":"q2_strictness_authority","value":7},{"question_id":"q3_control_need","value":8},{"question_id":"q4_praise_importance","value":5},{"question_id":"q5_novelty_challenge","value":8},{"question_id":"q6_intensity_1_5","value":4},{"question_id":"q8_instruction_style","value":"mixed"},{"question_id":"q9_open_context","value":"Heute nur kurze Session."}]}'

# 3) Setup abschliessen (erstellt aktive ChastitySession)
curl -X POST http://127.0.0.1:5000/api/v1/setup/sessions/<setup_session_id>/complete

# 4) Psychogramm nachkalibrieren
curl -X PATCH http://127.0.0.1:5000/api/v1/setup/sessions/<setup_session_id>/psychogram \
  -H "Content-Type: application/json" \
  -d '{"update_reason":"mid_session_calibration","trait_overrides":{"strictness_affinity":85}}'

# 5) Persistenten Story-Turn senden (session_id aus Setup-Complete verwenden)
curl -X POST http://127.0.0.1:5000/api/v1/story/turn \
  -H "Content-Type: application/json" \
  -d '{"session_id":"<session_id>","action":"I follow the instruction.","language":"en"}'
```

Browser-Demo:

```text
http://127.0.0.1:5000/api/v1/setup/demo
```

Mehrsprachigkeit (MVP):

- Unterstuetzte Sprachen: `de`, `en`
- Sprachwahl aktuell ueber API-Feld `language` im Setup-/Story-Request
- Fragebogen abrufen: `GET /api/v1/setup/questionnaire?language=de|en`

Setup-Persistenz (aktuell):

- Datei-basierter Store: `data/setup_sessions.json`
- Optional per Env steuerbar: `SETUP_STORE_PATH=/pfad/zur/datei.json`
- Relationale Persistenz: `DATABASE_URL` (default: `sqlite:///data/chastease.db`)

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

- Einstieg: `docs/PROJECT_DOCUMENTATION.md`
- Produktvision: `docs/PRODUCT_VISION.md`
- Anforderungen (SRS): `docs/REQUIREMENTS_SRS.md`
- UI/UX Anforderungen: `docs/UI_UX_REQUIREMENTS.md`
- Architektur: `docs/ARCHITECTURE.md`
- Umsetzungsplan (MVP): `docs/PROJECT_PLAN.md`
- Backlog: `docs/BACKLOG.md`
