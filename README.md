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

Frontend Start:

```text
http://127.0.0.1:5000/
```

Healthcheck:

```bash
curl http://127.0.0.1:5000/api/v1/health
```

## Docker Compose (Dev)

Option A (lokale Entwicklung mit Hot-Reload, SQLite in Docker-Volume):

```bash
docker compose up --build
```

App ist danach erreichbar unter:

```text
http://127.0.0.1:3000/
```

Wichtige Hinweise:

- Das Repo wird als Bind-Mount eingebunden (`./:/app`), daher wirken Codeaenderungen direkt mit Reload.
- Persistente Laufzeitdaten liegen im Docker-Volume `chastease_data` (`/app/data`).
- Fuer API-Keys/Secrets in Dev die gewuenschten Variablen beim `docker compose`-Start in der Shell setzen oder in `docker-compose.yml` ergaenzen.

## GitHub Action: manuelles Docker Image (GHCR)

Es gibt einen manuellen Workflow unter:

```text
Actions -> Manual Docker Image Build -> Run workflow
```

Optionen beim Start:

- `image_tag`: optionaler Tag (wenn leer: `manual-<run_number>`)
- `push_latest`: optional `true`, um zusaetzlich `:latest` zu pushen

Das Image wird nach GHCR gepusht unter:

```text
ghcr.io/amet-titulari/chastease:<tag>
```

## Portainer Stack (GHCR)

Fuer Portainer ist eine fertige Stack-Datei vorhanden:

- `docker-compose.portainer.yml`

Diese verwendet direkt das GHCR-Image:

```text
ghcr.io/amet-titulari/chastease:latest
```

Hinweise:

- Falls das Package privat ist, in Portainer vorher eine Registry fuer `ghcr.io` hinterlegen (GitHub User + PAT mit `read:packages`).
- Nach dem Deploy App unter `http://<host>:3000` erreichbar.

Setup-Prototyp:

```bash
# 0) Register (Username + Email + Passwort)
curl -X POST http://127.0.0.1:5000/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{"username":"wearer_demo","email":"wearer@example.com","password":"demo-pass-123"}'

# oder Login
curl -X POST http://127.0.0.1:5000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"wearer_demo","password":"demo-pass-123"}'

# 1) Setup starten (mit user_id)
curl -X POST http://127.0.0.1:5000/api/v1/setup/sessions \
  -H "Content-Type: application/json" \
  -d '{"user_id":"<user_id>","auth_token":"<auth_token>","hard_stop_enabled":true,"autonomy_mode":"execute","language":"de","integrations":["ttlock"],"blocked_trigger_words":["public"],"forbidden_topics":["workplace"]}'

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

Prototype App:

```text
http://127.0.0.1:5000/app
```

AI Chat UI:

```text
http://127.0.0.1:5000/chat
```

Hinweis zu Datei-Antworten der KI:

- Chat-Responses koennen `generated_files` enthalten.
- Prototyp-Marker im Narration-Text: `[[FILE|{"name":"brief.txt","mime_type":"text/plain","content":"..."}]]`
- Diese Dateien werden im Chat als Download angeboten.

Mehrsprachigkeit (MVP):

- Unterstuetzte Sprachen: `de`, `en`
- Sprachwahl aktuell ueber API-Feld `language` im Setup-/Story-Request
- Fragebogen abrufen: `GET /api/v1/setup/questionnaire?language=de|en`

Setup-Persistenz (aktuell):

- Datei-basierter Store: `data/setup_sessions.json`
- Optional per Env steuerbar: `SETUP_STORE_PATH=/pfad/zur/datei.json`
- Relationale Persistenz: `DATABASE_URL` (default: `sqlite:///data/chastease.db`)
- Session-Kill-Feature (nur Test/Build): `ENABLE_SESSION_KILL=true|false` (default: `false`)
- Chaster API Basis-URL (optional): `CHASTER_API_BASE=https://api.chaster.app`
- Optionaler AI-Read-Token fuer Live-Session-Infos: `AI_SESSION_READ_TOKEN=<secret>`
- Auth-Tokens werden serverseitig in-memory gehalten (nach Server-Neustart ist Login erneut erforderlich)

Live-Session-Infos abrufen:

```bash
# Wearer-Zugriff mit LIGHT mode (nur Zeit/Status, minimal ~270 tokens, default)
curl "http://127.0.0.1:5000/api/v1/sessions/<session_id>/live?auth_token=<auth_token>&detail_level=light"

# Wearer-Zugriff mit FULL mode (inkl. Setup/Turns/Psychogram, ~350+ tokens)
curl "http://127.0.0.1:5000/api/v1/sessions/<session_id>/live?auth_token=<auth_token>&detail_level=full&recent_turns_limit=5"

# AI-/Service-Zugriff (ai_access_token, serverseitig gegen AI_SESSION_READ_TOKEN geprueft)
curl "http://127.0.0.1:5000/api/v1/sessions/<session_id>/live?ai_access_token=<ai_session_read_token>&detail_level=light"
```

**Detail Levels:**

- `light` (default): Nur `session_status` und `time_context` - minimal Token-Verbrauch für häufige Status-Checks
- `full`: Zusätzlich `setup_context`, `turns`, `session` (vollständiges Session-Objekt)

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
