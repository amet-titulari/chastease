# Architektur – Chastease

## Überblick

Chastease folgt einem privaten Client-Server-Modell für den Heimnetz-Betrieb.

- Backend: FastAPI-Anwendung auf einem lokalen Host (PC/NAS/Server).
- Persistenz: SQLite + lokale Medienablage unter `data/`.
- Clients: zustandsarme Browser-Clients ohne beabsichtigte langlebige App-Persistenz.
- Realtime: WebSocket-Stream für Chat-Events, proaktive Reminder und optionale Timer-Ticks.
- Hintergrundjobs: APScheduler für Task-Overdue, proaktive Nachrichten und Timer-Ablauf.

Deployment-Empfehlung:

- Zugriff im LAN direkt.
- Zugriff von extern nur über VPN (z.B. WireGuard/Tailscale), kein direktes Exposing ins Internet.

## Aktueller Architektur-Stand (v0.1.0)

### Application-Layer

- `app/main.py`: App-Bootstrap, Router-Registrierung, Scheduler-Setup, globale Fehlerbehandlung.
- Router:
  - `app/routers/sessions.py`: Session-Lifecycle, Contract/Addenda, Timer-Operationen, Event-Log/Export.
  - `app/routers/chat.py`: REST-Chat + WebSocket-Endpoint inkl. Token-Absicherung; KI-Actions-Dispatch.
  - `app/routers/safety.py`, `app/routers/verification.py`, `app/routers/hygiene.py`.
  - `app/routers/web.py`: Auth (Login/Register/Logout), Seiten-Rendering; Token bleibt bei Re-Login erhalten (Multi-Device-Support).
  - `app/routers/tasks.py`: Task-CRUD, Status-Updates.

### Domain-/Service-Layer

- `app/services/task_service.py`: Task-Logik inkl. Konsequenzen (Zeitstrafe, Zeitbonus).
- `app/services/task_sweeper.py`: automatische Overdue-Auswertung für aktive Sessions.
- `app/services/proactive_messaging.py`: proaktive Assistant-Nachrichten mit Cooldown.
- `app/services/session_timer_sweeper.py`: automatisches Session-Ende bei Timer-Ablauf.
- `app/services/ai_gateway.py`: KI-Provider-Abstraktion (`CustomOpenAI`, `Ollama`, `Stub`); Action-Normalisierung.
- `app/services/prompt_builder.py`: Aufbau des System-Prompts inkl. Persona, Grenzen, offene Tasks.

### KI-Actions-Flow

Die KI gibt strukturierte JSON-Actions zurück. `normalize_actions()` in `ai_gateway.py` validiert und normalisiert diese. Aktuell unterstützte Action-Typen:

| Typ | Effekt |
|---|---|
| `create_task` | Legt neuen Task in der DB an, schickt Systemmeldung in den Chat |
| `add_time` | Verlängert den Session-Timer um N Minuten |
| `fail_task` | Markiert einen offenen Task als `failed`; löst Konsequenz aus |

Offene (pending) Tasks werden bei jedem Chat-Request als Kontext-Block in den System-Prompt injiziert, damit die KI sie kennt und referenzieren kann.

### Realtime-Layer

- Endpoint: `ws /api/sessions/{id}/chat/ws?token=<ws_auth_token>`.
- Stream-Inhalte:
  - Chat-Nachrichten (`chat`)
  - Proaktive Reminder (`proactive_reminder`)
  - Optional Timer-Ticks (`timer_tick`, mit `stream_timer=1`)
- Token-Rotation:
  - `POST /api/sessions/{id}/chat/ws-token/rotate`
  - Bestehende Verbindungen mit altem Token werden serverseitig invalidiert.

### Frontend-Layer (play.html / play.js)

- Single-Column-Layout (kein Aside-Panel); vollständig responsive mit `100dvh`.
- **Aktionskarten** werden inline nach dem letzten Chat-Eintrag gerendert (`plAppendActionCards`).
  - Pro offenem Task: eine Karte mit Buttons „Erledigt", „Fehlgeschlagen", „Verifizieren" (je nach Task-Konfiguration).
  - Verifikation läuft inline in der Karte (Foto-Upload → Analyse → Ergebnis).
- Task-Dropdown im Header ist read-only (Übersicht); Aktionen laufen nur über die Karten.
- Session-Info (Status, Ablaufzeit) im Settings-Drawer.
- Einstellungs-Drawer: Persona-Wechsel, Session-Info, Hygiene-Öffnung, Safety-Controls.

### Persistenz

- Alembic-Migrationen: `0001` (Initial Schema) bis `0004` (Verification linked task).
- Relevante Entitäten: `Session`, `Message`, `Task`, `Contract`/`Addendum`, `SafetyLog`, `Verification`, `HygieneOpening`, `SealHistory`, `AuthUser`, `PlayerProfile`, `LlmProfile`, `Persona`.
- `AuthUser.session_token`: einmaliges, dauerhaftes Auth-Token (httpOnly-Cookie `chastease_auth`, 30 Tage); wird nur beim ersten Login erzeugt.
- `PlayerProfile.preferences_json`: enthält `wearer_boundary`, `wearer_style`, `wearer_goal`, `scenario_preset` – direkt in den AI-Prompt übertragen.

## Security-by-Design (aktueller Stand)

- Optionales `CHASTEASE_ADMIN_SECRET` für sensible Steuer-Endpoints.
- Geschützte Steuer-Endpunkte validieren `X-Admin-Secret`, falls gesetzt.
- WebSocket-Verbindung erfordert gültiges Session-Token.
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
