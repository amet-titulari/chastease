# Chastease 🔒

Eine immersive, datenschutzfreundliche Web-Applikation für KI-gestützte Chastity-Sessions mit realistischer Keyholder-Persona.

## Projektübersicht

Chastease ermöglicht es Nutzenden, realistische Chastity-Sessions zu erleben, in denen eine KI die Rolle der Keyholderin übernimmt. Die Applikation nutzt einen privaten Backend-Server im Heimnetz; dort werden Sessiondaten, Konfigurationen und Verifikationsbilder gespeichert. Client-Geräte dienen als Browser-Zugänge und sollen absichtlich keine langlebigen App-Daten oder Verifikationsbilder in der lokalen Galerie behalten.

## Features (Übersicht)

- **KI-Keyholderin** – Anpassbare Persona mit konsistentem Charakter
- **Session-Mechanik** – Zufällige Sperrdauern, Timer-Management
- **Bildverifikation** – Optionale Verifikation mit nummerierten Plomben
- **Aufgaben-System** – Challenges mit Belohnungen und Bestrafungen
- **Sicherheitssystem** – Ampelsystem, Safeword, Emergency Release
- **Benachrichtigungen** – Timer, Erinnerungen, Nachrichten der Keyholderin
- **Web Test Console** – Interaktive Browser-Oberfläche für Core-Flows

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
- **Frontend**: Jinja2 + HTMX
- **Datenbank**: SQLite (lokal)
- **KI**: Abstraktionsschicht – Standard xAI (Grok), erweiterbar auf lokale LLMs

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

Wichtige API-Endpunkte:

- `GET /api/health`
- `POST /api/sessions`
- `GET /api/sessions/{id}`
- `POST /api/sessions/{id}/sign-contract`
- `POST /api/sessions/{id}/contract/addenda`
- `POST /api/sessions/{id}/contract/addenda/{addendum_id}/consent`
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

WebSocket Live-Feed:

- `GET/POST` Chat bleibt verfuegbar, zusaetzlich streamt `ws /api/sessions/{id}/chat/ws` neue Assistant-Nachrichten live.
- Enthalten sind normale Chat-Antworten und Scheduler-basierte `proactive_reminder`-Nachrichten.
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

## Lizenz

Privates Projekt – alle Rechte vorbehalten.
