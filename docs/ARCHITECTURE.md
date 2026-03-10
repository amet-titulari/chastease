# Architektur – Chastease

## Überblick

Chastease folgt einem privaten Client-Server-Modell fuer den Heimnetz-Betrieb.

- Backend: FastAPI-Anwendung auf einem lokalen Host (PC/NAS/Server).
- Persistenz: SQLite + lokale Medienablage unter `data/`.
- Clients: zustandsarme Browser-Clients ohne beabsichtigte langlebige App-Persistenz.
- Realtime: WebSocket-Stream fuer Chat-Events, proaktive Reminder und optionale Timer-Ticks.
- Hintergrundjobs: APScheduler fuer Task-Overdue, proaktive Nachrichten und Timer-Ablauf.

Deployment-Empfehlung:

- Zugriff im LAN direkt.
- Zugriff von extern nur ueber VPN (z.B. WireGuard/Tailscale), kein direktes Exposing ins Internet.

## Aktueller Architektur-Stand (Alpha)

### Application-Layer

- `app/main.py`: App-Bootstrap, Router-Registrierung, Scheduler-Setup, globale Fehlerbehandlung.
- Router:
  - `app/routers/sessions.py`: Session-Lifecycle, Contract/Addenda, Timer-Operationen, Event-Log/Export.
  - `app/routers/chat.py`: REST-Chat + WebSocket-Endpoint inkl. Token-Absicherung.
  - `app/routers/safety.py`, `app/routers/verification.py`, `app/routers/hygiene.py`, `app/routers/web.py`.

### Domain-/Service-Layer

- `app/services/task_service.py`: Task-Logik inkl. Konsequenzen.
- `app/services/task_sweeper.py`: automatische Overdue-Auswertung fuer aktive Sessions.
- `app/services/proactive_messaging.py`: proaktive Assistant-Nachrichten mit Cooldown.
- `app/services/session_timer_sweeper.py`: automatisches Session-Ende bei Timer-Ablauf.

### Realtime-Layer

- Endpoint: `ws /api/sessions/{id}/chat/ws?token=<ws_auth_token>`.
- Stream-Inhalte:
  - Chat-Nachrichten (`chat`)
  - Proaktive Reminder (`proactive_reminder`)
  - Optional Timer-Ticks (`timer_tick`, mit `stream_timer=1`)
- Token-Rotation:
  - `POST /api/sessions/{id}/chat/ws-token/rotate`
  - Bestehende Verbindungen mit altem Token werden serverseitig invalidiert.

### Persistenz

- Alembic-Stand: Migrationen `0001` bis `0006`.
- Relevante Entitaeten: Sessions, Messages, Tasks, Contracts/Addenda, Safety Logs, Verifications, Hygiene Openings, Seal History.
- Session-Modell enthaelt `ws_auth_token` fuer persistente WebSocket-Authentifizierung pro Session.

## Security-by-Design (aktueller Stand)

- Optionales `CHASTEASE_ADMIN_SECRET` fuer sensible Steuer-Endpoints.
- Geschuetzte Steuer-Endpunkte validieren `X-Admin-Secret`, falls gesetzt.
- WebSocket-Verbindung erfordert gueltiges Session-Token.
- Einheitliches API-Fehlerformat mit `request_id` und strukturiertem Fehlerobjekt.

Details siehe `docs/SECURITY.md`.

## Projektstruktur (vereinfacht)

```text
chastease/
├── app/
│   ├── main.py
│   ├── routers/
│   ├── services/
│   ├── models/
│   ├── templates/
│   └── static/
├── alembic/
├── docs/
├── tests/
├── data/                # lokal, gitignored
├── README.md
└── requirements.txt
```

## Betriebsfluss (vereinfacht)

```text
Browser Client
  -> HTTP API (Session/Tasks/Safety/Verification)
  -> WebSocket Chat Stream (token-basiert)

FastAPI Backend
  -> SQLAlchemy/SQLite Persistenz
  -> APScheduler Jobs (Task/Reminder/Timer)
  -> optionale KI-Provider (derzeit Stub-basiert fuer Teilbereiche)
```

## Offene Architektur-Themen

- Echte KI-Provider-Anbindung (Grok/Ollama/OpenAI-kompatibel) ueber produktive Gateway-Implementierungen.
- Rollen-/Identity-Konzept statt globalem Shared Secret.
- Browser Push Notifications fuer priorisierte Events.
