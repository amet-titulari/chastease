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
- `app/routers/scenarios.py`: Scenario-CRUD, Presets, Export/Import; Phasen inklusive `score_targets`, `phase_weight` und `min_phase_duration_hours`.
- `app/routers/lovense.py`: Toy-Provider-/Preset-API, Lovense-Connect, Preset-Ausloesung und Simulator-Zugriff.
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
- `app/services/task_template_pool.py`: reproduzierbare Task-Auswahl fuer persona-spezifische Fallbacks im Chat.
- `app/services/task_service.py`: Task-Logik inkl. Konsequenzen (Zeitstrafe, Zeitbonus), Psychogramm-basierte Multiplikatoren.
- `app/services/task_sweeper.py`: automatische Overdue-Auswertung für aktive Sessions (APScheduler-Job).
- `app/services/timer_service.py`: Zustandsloser Timer-Service (add/remove/freeze/unfreeze) mit `TimerState`-Dataclass.
- `app/services/session_service.py`: Session-Lifecycle (Vertrag signieren, lock_start/lock_end, Aktivierung).
- `app/services/session_timer_sweeper.py`: automatisches Session-Ende bei Timer-Ablauf (APScheduler-Job).
- `app/services/proactive_messaging.py`: proaktive Assistant-Nachrichten mit Cooldown/Burst-Limits (APScheduler-Job).
- `app/services/roleplay_progression.py`: Phasenlogik, Phasenpunkte je Session, Snapshot fuer Dashboard/Play.
- `app/services/contract_service.py`: KI-generierte Vertragstexte.
- `app/services/hygiene_service.py`: Hygiene-Logik (Due-Back-Zeiten, Overrun, Perioden-Berechnung).
- `app/services/verification_analysis.py`: Verifikationsfotos: heuristische Plomben-Prüfung + OpenAI-kompatible Vision-API-Analyse.
- `app/services/transcription_service.py`: Audio-Transkription via OpenAI-kompatiblem `/audio/transcriptions`-Endpoint.
- `app/services/persona_card_mapper.py`: externe Persona-Card-Formate (SillyTavern) in interne Strukturen mappen.
- `app/services/web_push_service.py`: Web-Push-Dispatch via pywebpush + VAPID-Keys.
- `app/services/pdf_export.py`: PDF-Erzeugung (Raw PDF 1.4, keine externe Lib).
- `app/services/audit_logger.py`: JSON-Lines Audit-Log (opt-in via `CHASTEASE_AUDIT_LOG_ENABLED`).
- `app/services/toy_profile.py` / `app/services/toy_presets.py`: Wearer-Default-Toys, Presets und Session-/Persona-Zuordnung.

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

**JavaScript**: Die Seitenskripte liegen weiter in `play.js`, `dashboard.js`, `experience.js`, `history.js`, `landing.js` und `setup.js`, werden in `v0.5` aber schrittweise entkoppelt. Gemeinsame UI-Helfer wie `ui_common.js` (DOM-Helfer und Pill-Listen), `ui_runtime.js` (JSON-Requests, Polling sowie gemeinsame Datums-/Dauer-/Countdown-Formatierung), `roleplay_ui.js` (Roleplay-/Phasen-Meter), `dashboard_session_ui.js` (Session-Rahmen, Persona-Auswahl und Profilzusammenfassung im Dashboard), `dashboard_roleplay_ui.js` (Dashboard-Szene, Beziehung, Phase und Langzeitdynamik), `dashboard_hygiene_ui.js` (Hygiene-Kontingent und Open/Relock-UI im Dashboard), `dashboard_runs_ui.js` (Run-History und Run-Report-Rendering im Dashboard), `dashboard_safety_ui.js` (Hygiene-/Safety-Event-Handling im Dashboard), `play_chat_ui.js` (Chat-Timeline, Bubble-Render, Warnbanner), `play_lovense_ui.js` (Toy-Status, Console-Rendering und KI-Plan-Anzeige), `play_lovense_controller.js` (Lovense-Bootstrap, Planverarbeitung und Toy-Steuerung), `play_shell_ui.js` (Dropdown-/Header-Menues im Play-Modus), `play_voice_ui.js` (Realtime-Voice-Status, Audio-Streaming und Toggle-Verhalten), `play_roleplay_state_ui.js` (Roleplay-Panel mit Szene, Phase, Beziehung und Langzeitdynamik), `play_session_ui.js` (Safety-, Hygiene- und Verifikations-Interaktionen im Play-Modus), `play_tasks_ui.js` (Task- und Action-Card-Rendering im Play-Modus), `inventory.js` (Inventarverwaltung mit Import/Export, Formularen und Inline-Edit), `personas.js` (Persona-Verwaltung mit Formular, Avatar-Upload, Import/Export und Task-Bibliothek), `scenarios.js` (Scenario-Verwaltung mit Presets, Phasen-/Lore-Editor und Inventar-Zuordnung), `game_module_settings.js` (Spielekonfiguration mit Modul-Cards, Schwellenwerten und Masken-Upload), `contract_view.js` (Markdown-/Tabellen-Rendering für Vertragsdetails), `profile.js` (LLM-/Audio-Testaktionen und Provider-Presets im Wearer-Profil), `admin_posture_matrix.js` (Posture-Matrix mit Filter, Bulk-Aktionen und Vorschau-Modal), `game_posture_manage.js` (Posture-Management mit ZIP-Import/Export, Karten-CRUD und Referenz-Skelett-Bearbeitung) und `game_posture.js` (Live-Spielbildschirm mit Kamera, Pose-/Movement-Analyse, Overlay-Rendering und Run-Steuerung) ziehen wiederverwendbare Render- und Handler-Logik aus den großen Seitendateien heraus; nur kleine Bootstrap-Datenblöcke bleiben direkt in einzelnen Templates eingebettet. Inline-Handler wie `onclick` in dynamisch gerenderten Listen wurden dabei auf delegierte Event-Listener umgestellt. Veraltete Lovense-Dashboard-Altlogik wurde entfernt, weil die Toy-Steuerung inzwischen ueber `/toys/{session_id}` laeuft.

**CSS**: Globale Tokens in `theme.css`, gemeinsame UI-Bausteine in `ui.css`, Layout/Navigation in `style.css`, modulbezogene Styles in `play.css`, `dashboard.css`, `experience.css`, `profile.css`, `landing.css`, `setup.css`. `ui.css` traegt inzwischen auch einfache Utility-Klassen wie `hidden`, `ok` und `warn`, damit sie nicht in mehreren Templates dupliziert werden.

**Play-Modus (play.html / play.js)**:
- Single-Column-Layout, vollständig responsive (`100dvh`).
- **Aktionskarten** inline nach `task_assigned`-Nachrichten in der Chat-Timeline.
  - Jede Karte zeigt Task-Nummer, Titel, Deadline (rechtsbündig mit Farb-Codierung) und kontextabhängige Buttons (Bestätigung + Fail oder Fotoverifikation + Fail).
  - Verifikation läuft komplett inline (Foto-Upload → Analyse → Ergebnis-Pill).
  - Render- und Handler-Logik fuer Dropdown- und Inline-Task-Cards liegt seit `v0.5` nicht mehr direkt in `play.js`, sondern in `play_tasks_ui.js`.
- Timeline-, Bubble- und Warnbanner-Rendering liegen seit `v0.5` nicht mehr direkt in `play.js`, sondern in `play_chat_ui.js`.
- Die Befuellung des Roleplay-Sidepanels liegt seit `v0.5` nicht mehr direkt in `play.js`, sondern in `play_roleplay_state_ui.js`.
- **Tasks-Dropdown** im Header zeigt interaktive Action Cards (nicht read-only).
- **Persona-Avatar** neben KI-Nachrichten (wenn Avatar in Persona hinterlegt).
- Session-Steuerung ist zwischen Dashboard und Play verteilt: Dashboard fuer Rahmen, Hygiene, Safety und Resultate; Play fuer Chat, Tasks und schnelle Safety-Aktionen.
- Relationship-Metriken und Phasenfortschritt sind bewusst getrennt:
  - `relationship_state_json`: langfristige Session-Gesamtbeurteilung
  - `phase_state_json`: aktuelle Phasenpunkte und Zielwerte der laufenden Phase
  - die gemeinsame Darstellung dieser Metriken wird in `roleplay_ui.js` fuer Dashboard und Play geteilt

### Persistenz

- Alembic-Stand: eine frische Initialmigration fuer den kompletten aktuellen Schema-Stand; leere Datenbanken koennen direkt mit `alembic upgrade head` aufgebaut werden.
- Entitäten (projektweit 25 Model-Dateien, Kernpersistenz u. a. fuer `AuthUser`, `Session`, `Message`, `Task`, `Contract`, `ContractAddendum`, `SafetyLog`, `Verification`, `HygieneOpening`, `SealHistory`, `PlayerProfile`, `LlmProfile`, `Persona`, `Scenario`, `Item`, `ScenarioItem`, `SessionItem`, `MediaAsset`, `PushSubscription`, Games-Run-Modelle).
- `AuthUser.session_token`: dauerhaftes Auth-Token (httpOnly-Cookie `chastease_auth`, 30 Tage).
- `AuthUser.password_hash`: moderner Passwort-Hash via `pwdlib`/Argon2; ältere SHA-256-Salt-Hashes werden beim Login migriert.
- `AuthUser.active_session_id`: FK zu aktiver Session (Play-Redirect nach Login).
- `AuthUser.default_player_profile_id`: FK zu Standard-Spielerprofil.
- `PlayerProfile.preferences_json`: enthält u. a. `wearer_boundary`, `wearer_style`, `wearer_goal`, `scenario_preset`, `scenario_phase_id`, Toy-Defaults und aktive Szenario-Prefs.
- `Persona.avatar_media_id`: FK zu `MediaAsset` (Avatar-Bild).
- `Session`: enthält pro-Session LLM-Config (`llm_provider`, `llm_api_url`, `llm_chat_model`, `llm_vision_model`).
- `Session.relationship_state_json`: langfristige Beziehungsmetriken der Session.
- `Session.phase_state_json`: aktuelle Phasenpunkte, Zielwerte und Startzeit der aktiven Phase.
- `Session.llm_api_key`, `LlmProfile.api_key` und die Session-State-JSON-Felder liegen im aktuellen Alpha-Stand bewusst als Klartext in SQLite, um Debugging und Usability-Tests zu vereinfachen.
- Diese temporaere Vereinfachung ist ein bekannter Hardening-Rueckschritt und muss vor Beta wieder durch At-Rest-Verschluesselung ersetzt werden.

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
│   ├── routers/          # 18 Router-Module
│   ├── services/         # 36 Service-Module
│   ├── models/           # 25 Model-Dateien
│   ├── templates/        # 21 Jinja2-Templates
│   └── static/           # JS (34), CSS (9), SW
├── alembic/
│   └── versions/         # 1 Initialmigration fuer den aktuellen Schema-Stand
├── docs/
├── tests/                # 46 Testmodule + conftest
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
