# Chastease 🔒

Eine immersive, datenschutzfreundliche Web-Applikation für KI-gestützte Chastity-Sessions mit realistischer Keyholder-Persona.

## Projektübersicht

Chastease ermöglicht es Nutzenden, realistische Chastity-Sessions zu erleben, in denen eine KI die Rolle der Keyholderin übernimmt. Die Applikation nutzt einen privaten Backend-Server im Heimnetz; dort werden Sessiondaten, Konfigurationen und Verifikationsbilder gespeichert. Client-Geräte dienen als Browser-Zugänge und sollen absichtlich keine langlebigen App-Daten oder Verifikationsbilder in der lokalen Galerie behalten.

## Features (Übersicht)

- **KI-Keyholderin** – Anpassbare Persona mit konsistentem Charakter
- **Session-Mechanik** – Zufällige Sperrdauern, Timer-Management
- **Bildverifikation** – Optionale Verifikation mit nummerierten Plomben
- **Aufgaben-System** – Challenges mit Belohnungen und Bestrafungen
- **Persona-Presets** – Vordefinierte Keyholder-Personas (u.a. `Ballet Sub Ella`)
- **Sicherheitssystem** – Ampelsystem, Safeword, Emergency Release
- **Benachrichtigungen** – Timer, Erinnerungen, Nachrichten der Keyholderin
- **Web Push** – Browser-Subscriptions und Test-Dispatch ueber Web Push API
- **Web Test Console** – Interaktive Browser-Oberfläche für Core-Flows
- **Responsive UI** – Optimiert fuer Desktop und mobile Geraete

## Dokumentation

| Dokument | Inhalt |
|---|---|
| [VISION.md](docs/VISION.md) | Projektziel, Zielgruppe, Werte |
| [REQUIREMENTS.md](docs/REQUIREMENTS.md) | Funktionale & nicht-funktionale Anforderungen |
| [ARCHITECTURE.md](docs/ARCHITECTURE.md) | Tech-Stack, Systemdesign |
| [USER_STORIES.md](docs/USER_STORIES.md) | Nutzungsszenarien |
| [AI_DESIGN.md](docs/AI_DESIGN.md) | Keyholder-Persona & Prompt-Engineering |
| [ROADMAP.md](docs/ROADMAP.md) | Priorisierte Feature-Planung |
| [SECURITY.md](docs/SECURITY.md) | Endpoint-Schutzmatrix & Sicherheitsregeln |

## Tech-Stack

- **Backend**: Python 3.12+ / FastAPI
- **Frontend**: Jinja2 + Vanilla JavaScript
- **Datenbank**: SQLite (lokal)
- **KI**: Abstraktionsschicht – Standard xAI (Grok), erweiterbar auf lokale LLMs
- **KI-Provider**: `stub` (default) oder `ollama` fuer Vertragsgenerierung

## Schnellstart

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
alembic upgrade head
python -m uvicorn app.main:app --reload
```

Falls bereits eine lokale `data/chastease.db` aus einer frueheren Version existiert:

```bash
alembic stamp head
```

App: `http://127.0.0.1:8000`

Zusatzseiten:

- Dashboard: `/`
- Session History: `/history`
- Contracts: `/contracts`

Wichtige API-Endpunkte:

- `GET /api/health`
- `POST /api/sessions`
- `GET /api/sessions/{id}`
- `GET /api/sessions/{id}/events`
- `GET /api/sessions/{id}/events/export`
- `GET /api/sessions/{id}/contract`
- `GET /api/sessions/{id}/contract/export`
- `POST /api/sessions/{id}/sign-contract`
- `POST /api/sessions/{id}/contract/addenda`
- `POST /api/sessions/{id}/contract/addenda/{addendum_id}/consent`
- `GET /api/sessions/{id}/timer`
- `POST /api/sessions/{id}/timer/add`
- `POST /api/sessions/{id}/timer/remove`
- `POST /api/sessions/{id}/timer/freeze`
- `POST /api/sessions/{id}/timer/unfreeze`
- `POST /api/sessions/{id}/hygiene/openings`
- `GET /api/sessions/{id}/hygiene/openings/{opening_id}`
- `POST /api/sessions/{id}/hygiene/openings/{opening_id}/relock`
- `POST /api/sessions/{id}/safety/traffic-light`
- `POST /api/sessions/{id}/safety/safeword`
- `POST /api/sessions/{id}/safety/emergency-release`
- `GET /api/sessions/{id}/safety/logs`
- `POST /api/sessions/{id}/verifications/request`
- `POST /api/sessions/{id}/verifications/{verification_id}/upload`
- `GET /api/sessions/{id}/verifications`
- `POST /api/sessions/{id}/messages`
- `GET /api/sessions/{id}/messages`
- `POST /api/sessions/{id}/tasks`
- `GET /api/sessions/{id}/tasks`
- `POST /api/sessions/{id}/tasks/evaluate-overdue`
- `POST /api/sessions/{id}/tasks/{task_id}/status`
- `POST /api/sessions/{id}/chat/ws-token/rotate`
- `GET /api/push/config`
- `GET /api/sessions/{id}/push/subscriptions`
- `POST /api/sessions/{id}/push/subscriptions`
- `DELETE /api/sessions/{id}/push/subscriptions/{subscription_id}`
- `POST /api/sessions/{id}/push/test`

Automatischer Task-Overdue-Sweep:

- Hintergrundjob (APScheduler) prueft periodisch alle aktiven Sessions auf ueberfaellige Tasks.
- Konfiguration per `.env`:
	- `CHASTEASE_TASK_OVERDUE_SWEEPER_ENABLED=true|false`
	- `CHASTEASE_TASK_OVERDUE_SWEEPER_INTERVAL_SECONDS=60`

Proaktive Keyholderin-Reminder:

- Hintergrundjob (APScheduler) erzeugt fuer aktive Sessions periodische Assistant-Reminder.
- Cooldown verhindert Spam (nur wenn keine frische Assistant-Nachricht vorliegt).
- Konfiguration per `.env`:
	- `CHASTEASE_PROACTIVE_MESSAGES_ENABLED=true|false`
	- `CHASTEASE_PROACTIVE_MESSAGES_INTERVAL_SECONDS=120`
	- `CHASTEASE_PROACTIVE_MESSAGES_COOLDOWN_SECONDS=600`

Automatisches Session-Ende bei Timer-Ablauf:

- Hintergrundjob (APScheduler) beendet aktive Sessions automatisch, sobald `lock_end` erreicht ist.
- Es wird ein `session_event` im Nachrichtenverlauf hinterlegt.
- Konfiguration per `.env`:
	- `CHASTEASE_SESSION_TIMER_SWEEPER_ENABLED=true|false`
	- `CHASTEASE_SESSION_TIMER_SWEEPER_INTERVAL_SECONDS=30`

WebSocket Live-Feed:

- `GET/POST` Chat bleibt verfuegbar, zusaetzlich streamt `ws /api/sessions/{id}/chat/ws` neue Assistant-Nachrichten live.
- Enthalten sind normale Chat-Antworten und Scheduler-basierte `proactive_reminder`-Nachrichten.
- Optional: mit `&stream_timer=1` werden zusaetzlich `timer_tick`-Events (`remaining_seconds`, `timer_frozen`) gestreamt.
- Zugriff auf den Chat-WebSocket erfordert `?token=<ws_auth_token>`.
- `ws_auth_token` wird aktuell in Session-Antworten (`POST /api/sessions`, `POST /api/sessions/{id}/sign-contract`, `GET /api/sessions/{id}`) mitgegeben.
- `POST /api/sessions/{id}/chat/ws-token/rotate` erzeugt ein neues Token und invalidiert bestehende WS-Verbindungen serverseitig.
- Optionaler Schutz: Wenn `CHASTEASE_ADMIN_SECRET` gesetzt ist, muss der Header `X-Admin-Secret` fuer Rotations-Endpunkte mitgesendet werden.
- Der gleiche optionale Schutz gilt auch fuer sicherheitskritische Steuer-Endpunkte:
	- `POST /api/sessions/{id}/safety/traffic-light`
	- `POST /api/sessions/{id}/safety/emergency-release`
	- `POST /api/sessions/{id}/verifications/{verification_id}/upload`

Tests ausführen:

```bash
python -m pytest -q
```

Fehlerformat (API):

- Einheitliches JSON fuer Fehlerantworten:
	- `request_id`
	- `error.code`
	- `error.message`
	- optional `error.details`

Sicherheit (Kurzfassung):

- Chat-WebSocket ist token-pflichtig (`ws_auth_token` pro Session).
- WS-Token-Rotation invalidiert alte Verbindungen serverseitig.
- Sensible Steuer-Endpunkte koennen optional mit `CHASTEASE_ADMIN_SECRET` + Header `X-Admin-Secret` geschuetzt werden.
- Vollstaendige Matrix: `docs/SECURITY.md`.

Operations-Hinweise:

- DB-Migrationen vor Start auf aktuellen Stand bringen: `alembic upgrade head`
- Tests im Projekt-Interpreter ausfuehren: `python -m pytest -q`
- Scheduler-Feature-Flags in `.env` setzen (Task-Sweep, Proactive Messages, Timer-Sweeper)

Ollama-Provider (optional):

- `CHASTEASE_AI_PROVIDER=ollama`
- `CHASTEASE_AI_OLLAMA_BASE_URL=http://127.0.0.1:11434`
- `CHASTEASE_AI_OLLAMA_MODEL=llama3.1`
- `CHASTEASE_AI_OLLAMA_TIMEOUT_SECONDS=15`
- Falls Ollama nicht erreichbar ist, faellt die Vertragsgenerierung automatisch auf den Stub zurueck.

Web Push (optional):

- `CHASTEASE_WEB_PUSH_ENABLED=true`
- `CHASTEASE_WEB_PUSH_VAPID_PUBLIC_KEY=<public_key>`
- `CHASTEASE_WEB_PUSH_VAPID_PRIVATE_KEY=<private_key>`
- `CHASTEASE_WEB_PUSH_VAPID_CLAIMS_SUB=mailto:admin@example.com`
- Fuer Dispatch wird `pywebpush` verwendet. Ohne gueltige VAPID-Konfiguration bleibt Dispatch deaktiviert.

KI-Bildanalyse fuer Verifikation:

- Default: `CHASTEASE_VERIFICATION_AI_PROVIDER=heuristic`
- Optional: `CHASTEASE_VERIFICATION_AI_PROVIDER=ollama`
- Modell/Timeout:
	- `CHASTEASE_VERIFICATION_OLLAMA_MODEL=llava`
	- `CHASTEASE_VERIFICATION_OLLAMA_TIMEOUT_SECONDS=20`
- Bei Fehlern/Nichterreichbarkeit des Ollama-Endpoints faellt die Analyse automatisch auf heuristische Auswertung zurueck.

## Lizenz

Privates Projekt – alle Rechte vorbehalten.
