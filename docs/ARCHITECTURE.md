# Architektur – Chastease

## Überblick

Chastease folgt einem privaten Client-Server-Modell für den Heimnetz-Betrieb.

- Backend: FastAPI-Anwendung auf einem lokalen Host (PC/NAS/Server).
- Persistenz: SQLite + lokale Medienablage unter `data/`.
- Clients: zustandsarme Browser-Clients ohne beabsichtigte langlebige App-Persistenz.
- Realtime: WebSocket-Stream für Chat-Events, proaktive Reminder und optionale Timer-Ticks.
- Hintergrundjobs: APScheduler für Task-Overdue, proaktive Nachrichten und Timer-Ablauf.
- Voice: optionale OpenAI-Realtime-Voice und TTS-Integration.

Deployment-Empfehlung:

- Zugriff im LAN direkt.
- Zugriff von extern nur über VPN (z.B. WireGuard/Tailscale), kein direktes Exposing ins Internet.

## Aktueller Architektur-Stand (März 2026)

### Application-Layer

- `app/main.py`: App-Bootstrap, Router-Registrierung, Scheduler-Setup, globale Fehlerbehandlung, CSRF-Middleware, `init_app_storage()` (Verzeichnisse + Alembic-Migration auf Startup).
- Router:
  - `app/routers/health.py`: Health-Check (`/health`), LLM-Verbindungstest.
  - `app/routers/sessions.py`: Session-Lifecycle, Blueprints, Contract/Addenda/Consent, Player-Profile, Seal-History, Timer (add/remove/freeze/unfreeze), WS-Token-Rotation, Event-Log/Export.
  - `app/routers/chat.py`: REST-Chat (GET/POST), Media-/Bild-Messages, Regenerate, WebSocket-Endpoint inkl. Token-Absicherung; KI-Actions-Dispatch.
  - `app/routers/tasks.py`: Task-CRUD, Status-Updates, Overdue-Evaluation.
  - `app/routers/safety.py`: Ampelsystem, Resume, Safeword, Emergency Release, Safety-Logs.
  - `app/routers/verification.py`: Verifikations-Request, Bild-Upload mit Analyse, Verifikations-Liste.
  - `app/routers/hygiene.py`: Hygiene-Quota, Öffnungen erstellen/abrufen, Relock.
  - `app/routers/personas.py`: Persona-CRUD, Presets, Scenario-Presets, Card-Schema, externe Card-Imports (SillyTavern-kompatibel), Export/Import.
  - `app/routers/scenarios.py`: Scenario-CRUD, Presets, Export/Import.
  - `app/routers/inventory.py`: Items-CRUD, Export/Import, Scenario-Item-Links, Session-Items.
  - `app/routers/inventory_postures.py`: modulbezogene Posture-Verwaltung und Matrix-Endpunkte im Inventar-Kontext.
  - `app/routers/media.py`: Avatar-Upload, Media-CRUD, Content-Serving.
  - `app/routers/push.py`: Web-Push-Config, Subscriptions, Test-Push.
  - `app/routers/voice.py`: Realtime-Voice-Status, Client-Secret (Ephemeral Key), TTS.
  - `app/routers/web.py`: Auth (Register/Login/Logout), Setup-Wizard, Profile (LLM, Audio, Restart-Setup), Experience-Onboarding, Play-Seite, History, Contracts, Personas, Scenarios, Inventory, Settings-Summary.

### Domain-/Service-Layer

- `app/services/ai_gateway.py`: KI-Provider-Abstraktion (`CustomOpenAI`, `Ollama`, `Stub`); Action-Normalisierung (`normalize_actions()`).
- `app/services/auth_password.py`: moderne Passwort-Hashes via `pwdlib`/Argon2 plus Legacy-Migrationspfad fuer alte SHA-256-Salt-Hashes.
- `app/services/prompt_builder.py`: Modularer System-Prompt (Persona, Wearer, Safety, Session, Style, Scenario); Strictness-Level-basierte deutsche Stil-Direktiven.
- `app/services/context_window.py`: Kontextfenster-Management (Nachrichtenhistorie, Trunkierung, Zusammenfassung älterer Nachrichten).
- `app/services/session_access.py`: zentrale Session-Ownership-Pruefungen fuer benutzergebundene APIs.
- `app/services/secret_crypto.py`: verschluesselte Speicherung sensibler API-Keys via `EncryptedText`.
- `app/services/task_template_pool.py`: reproduzierbare Task-Auswahl fuer persona-spezifische Fallbacks im Chat.
- `app/services/task_service.py`: Task-Logik inkl. Konsequenzen (Zeitstrafe, Zeitbonus), Psychogramm-basierte Multiplikatoren.
- `app/services/task_sweeper.py`: automatische Overdue-Auswertung für aktive Sessions (APScheduler-Job).
- `app/services/timer_service.py`: Zustandsloser Timer-Service (add/remove/freeze/unfreeze) mit `TimerState`-Dataclass.
- `app/services/session_service.py`: Session-Lifecycle (Vertrag signieren, lock_start/lock_end, Aktivierung).
- `app/services/session_timer_sweeper.py`: automatisches Session-Ende bei Timer-Ablauf (APScheduler-Job).
- `app/services/proactive_messaging.py`: proaktive Assistant-Nachrichten mit Cooldown/Burst-Limits (APScheduler-Job).
- `app/services/contract_service.py`: KI-generierte Vertragstexte.
- `app/services/hygiene_service.py`: Hygiene-Logik (Due-Back-Zeiten, Overrun, Perioden-Berechnung).
- `app/services/verification_analysis.py`: Verifikationsfotos: heuristische Plomben-Prüfung + OpenAI-kompatible Vision-API-Analyse.
- `app/services/transcription_service.py`: Audio-Transkription via OpenAI-kompatiblem `/audio/transcriptions`-Endpoint.
- `app/services/persona_card_mapper.py`: externe Persona-Card-Formate (SillyTavern) in interne Strukturen mappen.
- `app/services/web_push_service.py`: Web-Push-Dispatch via pywebpush + VAPID-Keys.
- `app/services/pdf_export.py`: PDF-Erzeugung (Raw PDF 1.4, keine externe Lib).
- `app/services/audit_logger.py`: JSON-Lines Audit-Log (opt-in via `CHASTEASE_AUDIT_LOG_ENABLED`).

### KI-Actions-Flow

Die KI gibt strukturierte JSON-Actions zurück. `normalize_actions()` in `ai_gateway.py` validiert und normalisiert diese. Aktuell unterstützte Action-Typen:

| Typ | Effekt |
|---|---|
| `create_task` | Legt neuen Task in der DB an, schickt Systemmeldung in den Chat |
| `add_time` | Verlängert den Session-Timer um N Minuten |
| `fail_task` | Markiert einen offenen Task als `failed`; löst Konsequenz aus |

Offene (pending) Tasks werden bei jedem Chat-Request als Kontext-Block in den System-Prompt injiziert, damit die KI sie kennt und referenzieren kann.

### Realtime-Layer

- Chat-WebSocket: `ws /api/sessions/{id}/chat/ws?token=<ws_auth_token>`.
  - Stream-Inhalte: Chat (`chat`), proaktive Reminder (`proactive_reminder`), Timer-Ticks (`timer_tick`, mit `stream_timer=1`).
  - Token-Rotation: `POST /api/sessions/{id}/chat/ws-token/rotate` invalidiert bestehende Verbindungen.
- Voice-WebSocket: optionaler OpenAI-Realtime-Audio-Stream.

### Frontend-Layer

**Templates** (Jinja2):

| Template | Zweck |
|---|---|
| `base.html` | Basis-Layout (Header, Nav, Footer, Assets) |
| `landing.html` | Landing / Login |
| `setup.html` | Setup-Wizard (4 Schritte: Stil, Ziel, Grenzen, KI) |
| `experience.html` | Experience-Onboarding / Session-Draft |
| `play.html` | Play-Modus (Chat + Aktionskarten) |
| `profile.html` | Profil-Settings (LLM, Audio, Setup-Neustart) |
| `games.html` | Spieleinstieg und Modul-Auswahl |
| `game_posture.html` / `game_posture_manage.html` / `game_module_settings.html` | Spiele- und Posture-Management |
| `history.html` | Session-History |
| `contracts.html` / `contract_view.html` | Vertragsübersicht / Vertrags-Detail |
| `personas.html` | Persona-Verwaltung |
| `scenarios.html` | Scenario-Verwaltung |
| `inventory.html` | Inventar-Verwaltung |

**JavaScript**: Zentrale Browserlogik liegt in `play.js`, `experience.js`, `history.js`, `landing.js` und `setup.js`; weitere Admin-/Games-Skripte sind direkt in Templates eingebettet.

**CSS**: Globale Tokens in `theme.css`, Layout/Navigation in `style.css`, modulbezogene Styles in `play.css`, `experience.css`, `profile.css`, `landing.css`, `setup.css`.

**Play-Modus (play.html / play.js)**:
- Single-Column-Layout, vollständig responsive (`100dvh`).
- **Aktionskarten** inline nach `task_assigned`-Nachrichten in der Chat-Timeline.
  - Jede Karte zeigt Task-Nummer, Titel, Deadline (rechtsbündig mit Farb-Codierung) und kontextabhängige Buttons (Bestätigung + Fail oder Fotoverifikation + Fail).
  - Verifikation läuft komplett inline (Foto-Upload → Analyse → Ergebnis-Pill).
- **Tasks-Dropdown** im Header zeigt interaktive Action Cards (nicht read-only).
- **Persona-Avatar** neben KI-Nachrichten (wenn Avatar in Persona hinterlegt).
- Session-Steuerung ist zwischen Dashboard und Play verteilt: Dashboard fuer Rahmen, Hygiene, Safety und Resultate; Play fuer Chat, Tasks und schnelle Safety-Aktionen.

### Persistenz

- Alembic-Migrationen: `0001` (Initial Schema) bis `0014` (Drop Scenarios Character Ref).
  - Alle Migrationen sind idempotent gestaltet (Existenz von Tabellen/Spalten/Indizes wird geprüft).
- Entitäten (20 Tabellen): `AuthUser`, `Session`, `Message`, `Task`, `Contract`, `ContractAddendum`, `SafetyLog`, `Verification`, `HygieneOpening`, `SealHistory`, `PlayerProfile`, `LlmProfile`, `Persona`, `Scenario`, `Item`, `ScenarioItem`, `SessionItem`, `MediaAsset`, `PushSubscription`.
- `AuthUser.session_token`: dauerhaftes Auth-Token (httpOnly-Cookie `chastease_auth`, 30 Tage).
- `AuthUser.password_hash`: moderner Passwort-Hash via `pwdlib`/Argon2; ältere SHA-256-Salt-Hashes werden beim Login migriert.
- `AuthUser.active_session_id`: FK zu aktiver Session (Play-Redirect nach Login).
- `AuthUser.default_player_profile_id`: FK zu Standard-Spielerprofil.
- `PlayerProfile.preferences_json`: enthält `wearer_boundary`, `wearer_style`, `wearer_goal`, `scenario_preset` – direkt in den AI-Prompt übertragen.
- `Persona.avatar_media_id`: FK zu `MediaAsset` (Avatar-Bild).
- `Session`: enthält pro-Session LLM-Config (`llm_provider`, `llm_api_url`, `llm_chat_model`, `llm_vision_model`).
- `Session.llm_api_key` und `LlmProfile.api_key`: verschluesselt via `EncryptedText`.

## Security-by-Design (aktueller Stand)

- Cookie-basierte Auth (`chastease_auth`, httpOnly, optional `Secure`, 30 Tage Gültigkeit).
- Browserbasierter CSRF-Schutz ueber Same-Origin-Pruefung plus CSRF-Header fuers Fetch-Layer.
- Session-Ownership-Scoping fuer benutzergebundene Session-APIs.
- Optionales `CHASTEASE_ADMIN_SECRET` als Zusatzschutz fuer besonders sensible Admin-Steuer-Endpoints.
- Admin-Steuer-Endpunkte wie `emergency-release` oder WS-Token-Rotation validieren `X-Admin-Secret`, falls gesetzt; Owner-Aktionen wie `traffic-light` oder Verifikations-Upload bleiben session-gescoped.
- WebSocket-Verbindung erfordert gültiges Session-Token.
- Einheitliches API-Fehlerformat mit `request_id` und strukturiertem Fehlerobjekt.
- Optionaler Audit-Logger (JSON-Lines, opt-in).

Details siehe `docs/SECURITY.md`.

## Projektstruktur (vereinfacht)

```text
chastease/
├── app/
│   ├── main.py
│   ├── config.py
│   ├── database.py
│   ├── security.py
│   ├── routers/          # 14 Router-Module
│   ├── services/         # 16 Service-Module
│   ├── models/           # 20 SQLAlchemy-Modelle
│   ├── templates/        # 13 Jinja2-Templates
│   └── static/           # JS (8), CSS (7), SW
├── alembic/
│   └── versions/         # 14 Migrationen (0001–0014)
├── docs/
├── tests/                # 31 Testmodule + conftest
├── scripts/              # Hilfs- und Remote-Volume-Skripte
├── data/                 # lokal, gitignored
├── README.md
└── requirements.txt
```

## Betriebsfluss (vereinfacht)

```text
Browser Client
  -> HTTP API (Session/Tasks/Safety/Verification/Hygiene/Personas/Scenarios/Inventory/Media)
  -> WebSocket Chat Stream (token-basiert)
  -> Optional: WebSocket Voice Stream (OpenAI Realtime)

FastAPI Backend
  -> SQLAlchemy/SQLite Persistenz
  -> APScheduler Jobs (Task-Overdue, Proaktive Nachrichten, Timer-Ablauf)
  -> KI-Provider (xAI/Grok, OpenRouter, Ollama, OpenAI-kompatibel)
  -> Vision-API fuer Verifikationsanalyse
  -> Web Push Notifications (pywebpush + VAPID)
```

## Offene Architektur-Themen

- Rollen-/Identity-Konzept statt Rest-Abhaengigkeit von globalem Shared Secret.
- Rate-Limits und Audit-Trails für sensible Endpunkte.
- Gamification-Layer (Achievements, Streaks, Statistiken).
